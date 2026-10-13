"""Test helpers for document ACL fixtures."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.access_group import AccessGroup, AccessGroupMembership
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.services.access_control.constants import VISIBILITY_ALL_STAFF, VISIBILITY_GROUPS
from app.services.access_control.groups import ensure_default_access_groups
from app.services.ingestion.indexer import FilePayload, index_files


def mark_source_visible_to_all_staff(source: Source) -> None:
    source.visibility_mode = VISIBILITY_ALL_STAFF
    source.visibility_group_ids = []
    source.visibility_user_ids = []


def employee_token(user_id: UUID, org_id: UUID, role: Role) -> str:
    return create_access_token(
        str(user_id),
        {
            "organization_id": str(org_id),
            "role": role.value,
            "aud": "aqrem-employee",
        },
    )


async def seed_acl_fixture_company(db: Session) -> dict:
    """Mixed-sensitivity org for ACL leak tests."""
    org = Organization(name="ACL Fixture Co", slug="acl-fixture")
    db.add(org)
    db.flush()
    ensure_default_access_groups(db, org.id)
    groups = {g.slug: g for g in db.query(AccessGroup).filter(AccessGroup.organization_id == org.id).all()}

    def user(email: str, name: str, role: Role) -> User:
        u = User(email=email, hashed_password=hash_password("test"), full_name=name)
        db.add(u)
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=u.id, role=role.value))
        return u

    admin = user("admin@acl.example", "Admin", Role.ORG_ADMIN)
    hr_mgr = user("hr@acl.example", "HR Manager", Role.EDITOR)
    fin_mgr = user("finance@acl.example", "Finance Manager", Role.EDITOR)
    employee = user("emp@acl.example", "Employee", Role.VIEWER)
    new_hire = user("newhire@acl.example", "New Hire", Role.VIEWER)
    removed = user("removed@acl.example", "Removed", Role.VIEWER)

    for u, slug in (
        (hr_mgr, "hr"),
        (fin_mgr, "finance"),
        (employee, "all-staff"),
        (new_hire, "all-staff"),
        (removed, "all-staff"),
    ):
        db.add(
            AccessGroupMembership(
                organization_id=org.id,
                group_id=groups[slug].id,
                user_id=u.id,
            )
        )
    db.flush()

    project = Project(organization_id=org.id, name="Company")
    db.add(project)
    db.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Company files",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
        visibility_mode=VISIBILITY_ALL_STAFF,
    )
    db.add(source)
    db.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db.add(job)
    db.flush()

    async def index_one(path: str, content: bytes, *, group_slug: str | None = None) -> None:
        from app.models.client_admin import ClientDocument

        file_name = path.split("/")[-1]
        mode = VISIBILITY_GROUPS if group_slug else VISIBILITY_ALL_STAFF
        gids = [groups[group_slug].id] if group_slug else []
        doc = ClientDocument(
            organization_id=org.id,
            source_id=source.id,
            file_name=file_name,
            content_type="text/plain",
            size_bytes=len(content),
            blob_path=f"{org.id}/{source.id}/{file_name}",
            status="indexed",
            visibility_mode=mode,
            visibility_group_ids=gids,
            acl_reviewed=True,
        )
        db.add(doc)
        db.flush()
        await index_files(
            db,
            source=source,
            job=job,
            files=[FilePayload(relative_path=path, data=content)],
        )

    await index_one("finance/payroll.csv", b"Karim salary 120000 MAD payroll", group_slug="finance")
    await index_one("hr/disciplinary_karim.txt", b"HR decided to issue written warning to Karim", group_slug="hr")
    await index_one("mgmt/exec_contract.txt", b"Executive employment contract confidential terms", group_slug="management")
    await index_one("policies/travel_policy.txt", b"Travel expense policy updated 2026: receipts required")
    await index_one("policies/onboarding.txt", b"Welcome onboarding guide for new employees")
    await index_one("sales/price_list.txt", b"Product price list 2026", group_slug="sales")
    db.flush()

    return {
        "org_id": org.id,
        "project_id": project.id,
        "admin": admin,
        "hr_mgr": hr_mgr,
        "fin_mgr": fin_mgr,
        "employee": employee,
        "new_hire": new_hire,
        "removed": removed,
        "groups": groups,
    }

"""Document-level ACL within an organization (SMB blocker)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import hash_password
from app.models.access_group import AccessGroup
from app.models.enums import EvidenceScope, SourceType, SyncJobStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source, SourceSyncJob
from app.models.client_admin import ClientDocument
from app.services.access_control.constants import VISIBILITY_GROUPS
from app.services.access_control.groups import ensure_default_access_groups
from app.services.ingestion.indexer import FilePayload, index_files
from tests.backend.helpers_acl import employee_token, mark_source_visible_to_all_staff

pytestmark = pytest.mark.usefixtures("document_acl_mode")


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_viewer_cannot_see_finance_only_salary(db_session, client: TestClient):
    org = Organization(name="SMB Co", slug="smb-co-acl")
    db_session.add(org)
    db_session.flush()
    ensure_default_access_groups(db_session, org.id)
    finance_group = db_session.query(AccessGroup).filter_by(organization_id=org.id, slug="finance").one()

    viewer = User(email="viewer@smb.example", hashed_password=hash_password("test"), full_name="Viewer")
    admin = User(email="admin@smb.example", hashed_password=hash_password("test"), full_name="Admin")
    db_session.add_all([viewer, admin])
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=viewer.id, role=Role.VIEWER.value))
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))

    project = Project(organization_id=org.id, name="HR")
    db_session.add(project)
    db_session.flush()

    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="HR uploads",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()

    doc = ClientDocument(
        organization_id=org.id,
        source_id=source.id,
        file_name="salary_confidential.txt",
        content_type="text/plain",
        size_bytes=40,
        blob_path=f"{org.id}/{source.id}/salary_confidential.txt",
        status="indexed",
        visibility_mode=VISIBILITY_GROUPS,
        visibility_group_ids=[finance_group.id],
        acl_reviewed=True,
    )
    db_session.add(doc)
    db_session.flush()

    await index_files(
        db_session,
        source=source,
        job=job,
        files=[
            FilePayload(
                relative_path="hr/salary_confidential.txt",
                data=b"Karim salary 120000 MAD - HR confidential",
            ),
        ],
    )
    db_session.flush()

    hv = _headers(employee_token(viewer.id, org.id, Role.VIEWER), str(org.id))
    ha = _headers(employee_token(admin.id, org.id, Role.ORG_ADMIN), str(org.id))

    rv = client.get("/api/v1/evidence", headers=hv)
    ra = client.get("/api/v1/evidence", headers=ha)
    assert rv.status_code == 200 and ra.status_code == 200
    assert rv.json()["total"] == 0
    assert ra.json()["total"] >= 1
    assert "salary" not in rv.text.lower()
    assert "120000" not in rv.text

    chat = client.post(
        "/api/v1/chat/ask",
        headers=hv,
        json={"query": "What is Karim's salary?", "project_id": str(project.id)},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert "120000" not in (body.get("answer") or "")
    assert "salary_confidential" not in chat.text.lower()


@pytest.mark.asyncio
async def test_all_staff_document_visible_to_viewer(db_session, client: TestClient):
    org = Organization(name="SMB Open", slug="smb-open")
    db_session.add(org)
    db_session.flush()
    viewer = User(email="viewer2@smb.example", hashed_password=hash_password("test"), full_name="Viewer")
    db_session.add(viewer)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=viewer.id, role=Role.VIEWER.value))
    project = Project(organization_id=org.id, name="Ops")
    db_session.add(project)
    db_session.flush()
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="Policies",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    mark_source_visible_to_all_staff(source)
    db_session.add(source)
    db_session.flush()
    job = SourceSyncJob(organization_id=org.id, source_id=source.id, status=SyncJobStatus.RUNNING.value)
    db_session.add(job)
    db_session.flush()
    await index_files(
        db_session,
        source=source,
        job=job,
        files=[FilePayload(relative_path="travel_policy.txt", data=b"Travel expense policy 2026")],
    )
    db_session.flush()
    hv = _headers(employee_token(viewer.id, org.id, Role.VIEWER), str(org.id))
    rv = client.get("/api/v1/evidence", headers=hv)
    assert rv.status_code == 200
    assert rv.json()["total"] >= 1

"""Adversarial cross-tenant and role boundary tests (two orgs)."""

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, LicenseStatus, SourceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org(db, name: str, slug: str, license_limit: int = 5) -> tuple[Organization, Project, User, str]:
    org = Organization(name=name, slug=slug, license_limit=license_limit)
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name=f"{name} Project")
    db.add(project)
    db.flush()
    user = User(email=f"{slug}@test.com", full_name=name, hashed_password=hash_password("password"))
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db.commit()
    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    return org, project, user, token


def test_cross_tenant_evidence_and_source_project(client, db_session):
    org_a, project_a, _user_a, token_a = _seed_org(db_session, "Org A", "org-a-e2e")
    org_b, project_b, _user_b, _token_b = _seed_org(db_session, "Org B", "org-b-e2e")

    source_b = Source(
        organization_id=org_b.id,
        project_id=project_b.id,
        name="B",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source_b)
    db_session.flush()
    evidence_b = EvidenceItem(
        organization_id=org_b.id,
        project_id=project_b.id,
        source_id=source_b.id,
        source_type=source_b.source_type,
        scope=source_b.scope,
        file_name="secret.md",
        file_path="secret.md",
        content="Org B only",
        content_hash="h1",
    )
    db_session.add(evidence_b)
    db_session.commit()

    h = _headers(token_a, str(org_a.id))
    assert client.get(f"/api/v1/evidence/{evidence_b.id}", headers=h).status_code in (403, 404)
    assert (
        client.post(
            "/api/v1/sources",
            headers=h,
            json={
                "name": "Bad",
                "source_type": SourceType.FOLDER_ARCHIVE.value,
                "scope": EvidenceScope.PROJECT.value,
                "project_id": str(project_b.id),
                "config": {},
            },
        ).status_code
        == 400
    )


def test_inactive_membership_rejected(client, db_session):
    org, _project, user, token = _seed_org(db_session, "Inactive Org", "inactive-org")
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id,
        )
        .one()
    )
    membership.is_active = False
    db_session.commit()
    res = client.get("/api/v1/projects", headers=_headers(token, str(org.id)))
    assert res.status_code == 403


def test_editor_cannot_call_org_admin_setup(client, db_session):
    org, _project, user, token = _seed_org(db_session, "Admin Org", "admin-org-e2e")
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.user_id == user.id,
        )
        .one()
    )
    membership.role = Role.EDITOR.value
    db_session.commit()
    res = client.get("/api/v1/org-admin/overview", headers=_headers(token, str(org.id)))
    assert res.status_code == 403


def test_tenant_user_cannot_call_master_admin(client, db_session):
    org, _project, _user, token = _seed_org(db_session, "Tenant", "tenant-master")
    res = client.get(
        "/api/v1/master/environments",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
    )
    assert res.status_code in (401, 403)


def test_production_blocks_zero_seat_active_org_sign_in(client, db_session, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "y" * 32)
    monkeypatch.setenv("LICENSING_TEST_MODE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    org = Organization(
        name="Prod Zero",
        slug="prod-zero",
        license_limit=0,
        license_status=LicenseStatus.ACTIVE.value,
        is_active=True,
    )
    user = User(email="prodzero@test.com", hashed_password=hash_password("password"), full_name="P")
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "prodzero@test.com", "password": "password", "organization_id": str(org.id)},
    )
    get_settings.cache_clear()
    assert res.status_code == 403

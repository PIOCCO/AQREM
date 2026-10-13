"""L1 platform vs L2/L3 tenant interface separation."""

from uuid import uuid4

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.source import Source


def _tenant_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _platform_token(user: User) -> str:
    return create_access_token(
        str(user.id),
        {
            "platform_role": user.platform_role,
            "platform_auth_version": int(user.platform_auth_version or 1),
        },
        audience=AUD_PLATFORM,
    )


def _seed_platform_super(db) -> tuple[User, str]:
    user = User(
        email=f"super-{uuid4().hex[:8]}@platform.test",
        full_name="Super",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, _platform_token(user)


def _seed_org_with_evidence(db, slug: str) -> tuple[Organization, EvidenceItem, User, str]:
    org = Organization(name=slug, slug=slug, license_limit=10, is_active=True)
    db.add(org)
    db.flush()
    project = Project(organization_id=org.id, name="P")
    db.add(project)
    db.flush()
    user = User(email=f"{slug}@test.com", full_name=slug, hashed_password=hash_password("password"))
    db.add(user)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=Role.ORG_ADMIN.value,
            is_active=True,
        )
    )
    source = Source(
        organization_id=org.id,
        project_id=project.id,
        name="S",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db.add(source)
    db.flush()
    evidence = EvidenceItem(
        organization_id=org.id,
        project_id=project.id,
        source_id=source.id,
        source_type=source.source_type,
        scope=source.scope,
        file_name="secret.md",
        file_path="secret.md",
        content="tenant-secret-content",
        content_hash="abc",
    )
    db.add(evidence)
    db.commit()
    token = create_access_token(
        str(user.id),
        {
            "organization_id": str(org.id),
            "role": Role.ORG_ADMIN.value,
            "auth_version": 1,
        },
        audience=AUD_ORG_ADMIN,
    )
    return org, evidence, user, token


def test_super_admin_can_manage_organizations(client, db_session):
    _user, token = _seed_platform_super(db_session)
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Sep Org", "license_limit": 5, "environment": "production"},
    )
    assert res.status_code == 201


def test_platform_token_cannot_read_tenant_evidence(client, db_session):
    _super_user, platform_tok = _seed_platform_super(db_session)
    org, evidence, _org_user, _tenant_tok = _seed_org_with_evidence(db_session, "evidence-org")
    res = client.get(
        f"/api/v1/evidence/{evidence.id}",
        headers=_tenant_headers(platform_tok, str(org.id)),
    )
    assert res.status_code in (401, 403)


def test_org_admin_cannot_call_platform_admin_api(client, db_session):
    org, _evidence, _user, tenant_tok = _seed_org_with_evidence(db_session, "org-admin-api")
    res = client.get(
        "/api/v1/admin/organizations",
        headers=_tenant_headers(tenant_tok, str(org.id)),
    )
    assert res.status_code in (401, 403)


def test_forged_organization_header_mismatch_rejected(client, db_session):
    org_a, _, _, tok_a = _seed_org_with_evidence(db_session, "org-a-sep")
    org_b, _, _, _ = _seed_org_with_evidence(db_session, "org-b-sep")
    res = client.get(
        "/api/v1/projects",
        headers=_tenant_headers(tok_a, str(org_b.id)),
    )
    assert res.status_code == 403


def test_org_admin_can_access_org_admin_overview(client, db_session):
    org, _, _user, tok = _seed_org_with_evidence(db_session, "overview-org")
    res = client.get("/api/v1/org-admin/overview", headers=_tenant_headers(tok, str(org.id)))
    assert res.status_code == 200


def test_editor_cannot_escalate_via_org_admin(client, db_session):
    org = Organization(name="Esc", slug="esc-org", license_limit=5, is_active=True)
    db_session.add(org)
    db_session.flush()
    user = User(email="editor@esc.test", full_name="E", hashed_password=hash_password("password"))
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value, is_active=True)
    )
    db_session.commit()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    res = client.get("/api/v1/org-admin/overview", headers=_tenant_headers(token, str(org.id)))
    assert res.status_code == 403

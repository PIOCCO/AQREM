"""Extended L1/L2/L3 separation: tokens, cross-tenant, exports, escalation, suspended orgs."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import get_settings
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import ALGORITHM, create_access_token, hash_password
from app.models.enums import EvidenceScope, SourceType
from app.models.evidence import EvidenceItem
from app.models.organization import Organization, OrganizationMembership, User
from app.models.project import Project
from app.models.questionnaire import Question, Questionnaire
from app.models.source import Source
from app.services.questionnaire.normalize import normalize_question


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org(
    db,
    slug: str,
    *,
    role: str = Role.ORG_ADMIN.value,
    active: bool = True,
) -> tuple[Organization, User, str]:
    org = Organization(name=slug, slug=slug, license_limit=10, is_active=active)
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
            role=role,
            is_active=True,
        )
    )
    db.commit()
    aud = AUD_ORG_ADMIN if role == Role.ORG_ADMIN.value else AUD_EMPLOYEE
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": role, "auth_version": 1},
        audience=aud,
    )
    return org, user, token


def _seed_platform(db) -> tuple[User, str]:
    user = User(
        email=f"plat-{uuid4().hex[:8]}@platform.test",
        full_name="Plat",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()
    token = create_access_token(
        str(user.id),
        {"platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )
    return user, token


def _seed_questionnaire(db, org: Organization, project: Project) -> Questionnaire:
    qn = Questionnaire(organization_id=org.id, name="Q", project_id=project.id)
    db.add(qn)
    db.flush()
    db.add(
        Question(
            organization_id=org.id,
            questionnaire_id=qn.id,
            external_id="1",
            text="Q?",
            normalized_text=normalize_question("Q?"),
            sort_order=0,
        )
    )
    db.commit()
    return qn


def test_tenant_jwt_cannot_access_master_environments(client: TestClient, db_session):
    org, _, tenant_tok = _seed_org(db_session, "tenant-master-block")
    res = client.get("/api/v1/master/environments", headers=_headers(tenant_tok, str(org.id)))
    assert res.status_code in (401, 403)


def test_platform_jwt_cannot_access_org_admin_overview(client: TestClient, db_session):
    org, _, _ = _seed_org(db_session, "plat-org-admin-block")
    _, plat_tok = _seed_platform(db_session)
    res = client.get("/api/v1/org-admin/overview", headers=_headers(plat_tok, str(org.id)))
    assert res.status_code in (401, 403)


def test_employee_cannot_create_platform_organization(client: TestClient, db_session):
    org, _, tok = _seed_org(db_session, "emp-plat", role=Role.EDITOR.value)
    before = db_session.query(Organization).count()
    res = client.post(
        "/api/v1/admin/organizations",
        headers=_headers(tok, str(org.id)),
        json={"name": "Evil Org", "license_limit": 5, "environment": "production"},
    )
    assert res.status_code in (401, 403)
    assert db_session.query(Organization).count() == before


def test_org_a_cannot_export_org_b_questionnaire(client: TestClient, db_session):
    org_a, _, tok_a = _seed_org(db_session, "export-a")
    org_b, _, _ = _seed_org(db_session, "export-b")
    project_b = db_session.query(Project).filter(Project.organization_id == org_b.id).one()
    qn_b = _seed_questionnaire(db_session, org_b, project_b)
    res = client.get(
        f"/api/v1/questionnaires/{qn_b.id}/export/csv",
        headers=_headers(tok_a, str(org_a.id)),
    )
    assert res.status_code in (403, 404)


def test_cross_tenant_evidence_download_not_found(client: TestClient, db_session):
    org_a, _, tok_a = _seed_org(db_session, "ev-a")
    org_b, _, _ = _seed_org(db_session, "ev-b")
    project_b = db_session.query(Project).filter(Project.organization_id == org_b.id).one()
    source = Source(
        organization_id=org_b.id,
        project_id=project_b.id,
        name="S",
        source_type=SourceType.FOLDER_ARCHIVE.value,
        scope=EvidenceScope.PROJECT.value,
    )
    db_session.add(source)
    db_session.flush()
    evidence = EvidenceItem(
        organization_id=org_b.id,
        project_id=project_b.id,
        source_id=source.id,
        source_type=source.source_type,
        scope=source.scope,
        file_name="x.md",
        file_path="x.md",
        content="secret-b",
        content_hash="h",
    )
    db_session.add(evidence)
    db_session.commit()
    res = client.get(f"/api/v1/evidence/{evidence.id}", headers=_headers(tok_a, str(org_a.id)))
    assert res.status_code == 404


def test_missing_auth_header_rejected(client: TestClient, db_session):
    org, _, _ = _seed_org(db_session, "no-auth")
    res = client.get("/api/v1/projects", headers={"X-Organization-Id": str(org.id)})
    assert res.status_code == 401


def test_malformed_bearer_token_rejected(client: TestClient, db_session):
    org, _, _ = _seed_org(db_session, "bad-tok")
    res = client.get("/api/v1/projects", headers=_headers("not-a-jwt", str(org.id)))
    assert res.status_code == 401


def test_wrong_audience_on_tenant_endpoint(client: TestClient, db_session):
    org, user, _ = _seed_org(db_session, "wrong-aud")
    wrong = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "auth_version": 1},
        audience=AUD_PLATFORM,
    )
    res = client.get("/api/v1/projects", headers=_headers(wrong, str(org.id)))
    assert res.status_code == 401


def test_expired_token_rejected_on_admin_api(client: TestClient, db_session):
    settings = get_settings()
    org, user, _ = _seed_org(db_session, "exp-admin")
    from datetime import UTC, datetime, timedelta

    expired = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(UTC) - timedelta(minutes=1),
            "iss": settings.jwt_issuer,
            "aud": AUD_ORG_ADMIN,
            "organization_id": str(org.id),
            "role": Role.ORG_ADMIN.value,
            "auth_version": 1,
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    res = client.get("/api/v1/org-admin/overview", headers=_headers(expired, str(org.id)))
    assert res.status_code == 401


def test_org_admin_invite_rejects_platform_admin_role(client: TestClient, db_session):
    org, _, tok = _seed_org(db_session, "esc-invite")
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_headers(tok, str(org.id)),
        json={"email": "p@example.com", "full_name": "P", "role": "PLATFORM_ADMIN"},
    )
    assert res.status_code == 400
    body = res.json()
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    assert detail.get("code") == "INVALID_ROLE"


def test_suspended_organization_blocks_tenant_api(client: TestClient, db_session):
    org, _, tok = _seed_org(db_session, "suspended-org", active=False)
    res = client.get("/api/v1/projects", headers=_headers(tok, str(org.id)))
    assert res.status_code == 403


def test_forged_org_header_does_not_mutate_other_org(client: TestClient, db_session):
    org_a, _, tok_a = _seed_org(db_session, "mut-a")
    org_b, _, _ = _seed_org(db_session, "mut-b")
    name_before = db_session.get(Organization, org_b.id).name
    res = client.patch(
        f"/api/v1/admin/organizations/{org_b.id}",
        headers=_headers(tok_a, str(org_b.id)),
        json={"name": "Hacked"},
    )
    assert res.status_code in (401, 403)
    db_session.refresh(org_b)
    assert org_b.name == name_before

"""Org admin cannot assign ORG_ADMIN; platform super admin can."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.audit import AuditEvent
from app.models.organization import Organization, OrganizationMembership, User
from app.services.org_admin.role_assignment import ORG_ADMIN_ASSIGN_FORBIDDEN_MESSAGE


def _org_admin_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org_admin(db_session) -> tuple[Organization, User, str]:
    org = Organization(name="Role Guard Co", slug=f"rg-{uuid4().hex[:8]}", license_limit=10)
    db_session.add(org)
    db_session.flush()
    admin = User(
        email=f"oa-{uuid4().hex[:6]}@test.local",
        full_name="Org Admin",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value, is_active=True)
    )
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
        audience=AUD_ORG_ADMIN,
    )
    return org, admin, token


def _super_admin_token(db_session) -> str:
    user = User(
        email=f"super-{uuid4().hex[:6]}@test.local",
        full_name="Super",
        hashed_password=hash_password("x"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )


def test_org_admin_invite_editor_allowed(client: TestClient, db_session):
    org, _, tok = _seed_org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_org_admin_headers(tok, str(org.id)),
        json={"email": "editor@example.com", "full_name": "Ed", "role": "EDITOR"},
    )
    assert res.status_code == 201, res.text


def test_org_admin_invite_viewer_allowed(client: TestClient, db_session):
    org, _, tok = _seed_org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_org_admin_headers(tok, str(org.id)),
        json={"email": "viewer@example.com", "full_name": "Vi", "role": "VIEWER"},
    )
    assert res.status_code == 201, res.text


def test_org_admin_invite_org_admin_forbidden(client: TestClient, db_session):
    org, admin, tok = _seed_org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_org_admin_headers(tok, str(org.id)),
        json={"email": "evil@example.com", "full_name": "Evil", "role": "ORG_ADMIN"},
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail["code"] == "ORG_ADMIN_ASSIGN_FORBIDDEN"
    assert ORG_ADMIN_ASSIGN_FORBIDDEN_MESSAGE in detail["message"]

    denied = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.organization_id == org.id,
            AuditEvent.user_id == admin.id,
            AuditEvent.action == "role_assignment_denied",
        )
        .order_by(AuditEvent.id.desc())
        .first()
    )
    assert denied is not None
    assert denied.event_metadata.get("attempted_role") == "ORG_ADMIN"


@pytest.mark.parametrize("role_payload", ["org_admin", " Org_Admin ", "ORG_ADMIN"])
def test_org_admin_invite_org_admin_casing_rejected(client: TestClient, db_session, role_payload: str):
    org, _, tok = _seed_org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers=_org_admin_headers(tok, str(org.id)),
        json={"email": f"case-{uuid4().hex[:4]}@example.com", "full_name": "Case", "role": role_payload},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ORG_ADMIN_ASSIGN_FORBIDDEN"


def test_org_admin_cannot_patch_member_to_org_admin_via_platform_api(client: TestClient, db_session):
    org, admin, oa_tok = _seed_org_admin(db_session)
    editor = User(email=f"ed-{uuid4().hex[:6]}@test.local", full_name="Ed", hashed_password=hash_password("x"), is_active=True)
    db_session.add(editor)
    db_session.flush()
    editor_m = OrganizationMembership(
        organization_id=org.id, user_id=editor.id, role=Role.EDITOR.value, is_active=True
    )
    db_session.add(editor_m)
    db_session.commit()

    res = client.patch(
        f"/api/v1/admin/organizations/{org.id}/members/{editor_m.id}",
        headers=_org_admin_headers(oa_tok, str(org.id)),
        json={"role": "ORG_ADMIN"},
    )
    assert res.status_code in (401, 403)


def test_org_admin_cannot_deactivate_other_org_member(client: TestClient, db_session):
    org_a, _, tok_a = _seed_org_admin(db_session)
    org_b, _, _ = _seed_org_admin(db_session)
    victim = (
        db_session.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == org_b.id)
        .first()
    )
    res = client.post(
        f"/api/v1/org-admin/members/{victim.id}/deactivate",
        headers=_org_admin_headers(tok_a, str(org_a.id)),
    )
    assert res.status_code == 404


def test_org_admin_cannot_remove_org_admin_row(client: TestClient, db_session):
    org, admin, tok = _seed_org_admin(db_session)
    admin_m = (
        db_session.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == admin.id, OrganizationMembership.organization_id == org.id)
        .one()
    )
    res = client.post(
        f"/api/v1/org-admin/members/{admin_m.id}/deactivate",
        headers=_org_admin_headers(tok, str(org.id)),
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ORG_ADMIN_REMOVE_FORBIDDEN"


def test_super_admin_provisions_org_admin_invite(client: TestClient, db_session):
    super_tok = _super_admin_token(db_session)
    create = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {super_tok}"},
        json={"name": "New Org", "license_limit": 2, "environment": "production"},
    )
    assert create.status_code == 201, create.text
    org_id = create.json()["id"]
    prov = client.post(
        f"/api/v1/admin/organizations/{org_id}/users",
        headers={"Authorization": f"Bearer {super_tok}"},
        json={"email": "newadmin@client.example", "full_name": "Client Admin", "role": "ORG_ADMIN"},
    )
    assert prov.status_code == 201, prov.text
    assert prov.json()["role"] == "ORG_ADMIN"

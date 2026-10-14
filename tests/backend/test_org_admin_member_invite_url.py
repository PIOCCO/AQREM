"""Org-admin member invite returns absolute URL; name and pending status."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_ORG_ADMIN
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _org_admin(db_session) -> tuple[Organization, str]:
    org = Organization(name="Invite URL Org", slug=f"iu-{uuid4().hex[:8]}", license_limit=10)
    db_session.add(org)
    db_session.flush()
    admin = User(
        email=f"oa-{uuid4().hex[:6]}@test.local",
        full_name="Admin",
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
    return org, token


def test_member_invite_returns_absolute_url(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://dev.example.com:5173")
    from app.core.config import get_settings

    get_settings.cache_clear()
    org, token = _org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
        json={"email": "newhire@example.com", "full_name": "test", "role": "VIEWER"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["invitation_setup_url"] == "https://dev.example.com:5173/invite/member/" + body[
        "invitation_setup_path"
    ].split("/invite/member/", 1)[1]
    assert body["invite_url"] == body["invitation_setup_url"]

    members = client.get(
        "/api/v1/org-admin/members",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
    ).json()
    row = next(m for m in members if m["email"] == "newhire@example.com")
    assert row["full_name"] == "test"
    assert row["membership_status"] == "pending"

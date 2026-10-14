"""Org-admin member invite returns absolute invite_url."""

from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _org_admin_headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed_org_admin(db_session) -> tuple[Organization, User, str]:
    org = Organization(name="Invite Co", slug="invite-co-url", license_limit=10)
    db_session.add(org)
    db_session.flush()
    admin = User(email="orgadmin@invite-url.test", full_name="Admin", hashed_password=hash_password("password"))
    db_session.add(admin)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value),
    )
    db_session.commit()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    return org, admin, token


@pytest.fixture()
def public_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://dev.example.com:5173")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_member_invite_returns_full_url(client: TestClient, db_session, public_url):
    org, _, token = _seed_org_admin(db_session)
    res = client.post(
        "/api/v1/org-admin/members/invite",
        json={"email": "newhire@example.com", "full_name": "New Hire", "role": "VIEWER"},
        headers=_org_admin_headers(token, str(org.id)),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["invitation_setup_url"].startswith("https://dev.example.com:5173/invite/member/")
    assert body["invite_url"] == body["invitation_setup_url"]
    path = body["invitation_setup_path"]
    assert path.startswith("/invite/member/")
    assert body["invitation_setup_url"].endswith(path)
    token_part = unquote(path.split("/invite/member/", 1)[1])
    assert token_part

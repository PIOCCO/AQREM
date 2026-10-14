"""API returns full invitation_setup_url and join_url."""

from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.organization import User


def _super(db_session) -> tuple[User, str]:
    user = User(
        email="super@url.test",
        full_name="Super",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
        platform_role=PlatformRole.SUPER_ADMIN.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    tok = create_access_token(
        str(user.id),
        {"platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )
    return user, tok


def test_create_admin_invitation_returns_full_url(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://aqrem.example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    _, token = _super(db_session)
    org = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "URL Org", "license_limit": 5, "environment": "production"},
    ).json()
    created = client.post(
        f"/api/v1/admin/organizations/{org['id']}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "admin@corp.example", "full_name": "Admin"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["invitation_setup_url"].startswith("https://aqrem.example.com/invite/admin/")
    assert body["invitation_setup_path"].startswith("/invite/admin/")
    raw = unquote(body["invitation_setup_path"].split("/invite/admin/", 1)[1])
    preview = client.post("/api/v1/auth/accept-invitation/preview", json={"token": raw})
    assert preview.status_code == 200


def test_employee_link_returns_join_url(client: TestClient, db_session, monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://aqrem.example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    _, token = _super(db_session)
    org = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Join URL Org", "license_limit": 5, "environment": "production"},
    ).json()
    link = client.post(
        f"/api/v1/admin/organizations/{org['id']}/employee-link",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_domains": ["corp.example"]},
    )
    assert link.status_code == 201
    body = link.json()
    assert body["join_url"].startswith("https://aqrem.example.com/join/")
    assert body["join_path"].startswith("/join/")

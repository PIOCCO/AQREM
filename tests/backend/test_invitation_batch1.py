"""Batch 1: invitation routing, history retention, link retrieval."""

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.invitation import UserInvitation
from app.models.organization import User


def _super(db_session) -> tuple[User, str]:
    user = User(
        email="super@batch1.test",
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


def _org(client: TestClient, token: str) -> str:
    res = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Batch1 Org", "license_limit": 5, "environment": "production"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_expired_admin_invite_stays_in_history(client: TestClient, db_session):
    _, token = _super(db_session)
    org_id = _org(client, token)
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "exp@corp.example", "full_name": "Exp Admin", "expires_days": 7},
    )
    assert created.status_code == 201
    inv_id = created.json()["invitation_id"]
    row = db_session.get(UserInvitation, inv_id)
    assert row is not None
    row.expires_at = row.expires_at - timedelta(days=30)
    db_session.commit()

    history = client.get(
        f"/api/v1/admin/organizations/{org_id}/invitations/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert history.status_code == 200
    match = [r for r in history.json() if r["id"] == inv_id]
    assert len(match) == 1
    assert match[0]["status"] == "expired"


def test_fetch_admin_invitation_link_for_pending(client: TestClient, db_session):
    _, token = _super(db_session)
    org_id = _org(client, token)
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "link@corp.example", "full_name": "Link Admin"},
    )
    assert created.status_code == 201
    inv_id = created.json()["invitation_id"]
    link = client.get(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin/{inv_id}/link",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert link.status_code == 200
    path = link.json()["invitation_setup_path"]
    assert path.startswith("/invite/admin/")
    from urllib.parse import unquote

    raw = unquote(path.split("/invite/admin/", 1)[1])
    preview = client.post("/api/v1/auth/accept-invitation/preview", json={"token": raw})
    assert preview.status_code == 200


def test_delete_accepted_invite_keeps_membership(client: TestClient, db_session):
    _, token = _super(db_session)
    org_id = _org(client, token)
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "done@corp.example", "full_name": "Done Admin"},
    )
    inv_id = created.json()["invitation_id"]
    from urllib.parse import unquote

    raw = unquote(created.json()["invitation_setup_path"].split("/invite/admin/", 1)[1])
    accept = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": raw, "password": "securepass1", "full_name": "Done Admin"},
    )
    assert accept.status_code == 200
    deleted = client.delete(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin/{inv_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204
    me = client.get(
        "/api/v1/org-admin/overview",
        headers={
            "Authorization": f"Bearer {accept.json()['access_token']}",
            "X-Organization-Id": str(accept.json()["organization_id"]),
        },
    )
    assert me.status_code == 200

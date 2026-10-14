"""Delete invitation / employee link history rows."""

from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.platform_roles import PlatformRole
from app.core.security import create_access_token, hash_password
from app.models.invitation import UserInvitation
from app.models.organization import User


def _super(db_session) -> tuple[User, str]:
    user = User(
        email="hist-del-super@example.com",
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
        {"aud": "aqrem-master", "platform_role": user.platform_role, "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )
    return user, tok


def test_delete_admin_invitation_history_post(client: TestClient, db_session):
    _, token = _super(db_session)
    org_id = client.post(
        "/api/v1/admin/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hist Del Org", "license_limit": 5, "environment": "production"},
    ).json()["id"]
    created = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "del@corp.example", "full_name": "Del Admin", "expires_days": 7},
    )
    assert created.status_code == 201
    inv_id = created.json()["invitation_id"]
    deleted = client.post(
        f"/api/v1/admin/organizations/{org_id}/invitations/admin/{inv_id}/delete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204, deleted.text
    assert db_session.get(UserInvitation, inv_id) is None
    history = client.get(
        f"/api/v1/admin/organizations/{org_id}/invitations/history",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert not any(row["id"] == str(inv_id) for row in history)

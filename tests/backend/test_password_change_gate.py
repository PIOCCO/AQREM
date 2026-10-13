"""Forced password change must block tenant APIs until completed."""

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_tenant_api_blocked_until_password_changed(client, db_session):
    org = Organization(name="Pwd Org", slug="pwd-org", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(
        email="mustchange@test.com",
        full_name="User",
        hashed_password=hash_password("old-password"),
        must_change_password=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value)
    )
    db_session.commit()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    blocked = client.get("/api/v1/projects", headers=_headers(token, str(org.id)))
    assert blocked.status_code == 403
    assert "password" in blocked.json()["detail"].lower()

    ok = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"current_password": "old-password", "new_password": "new-password-12"},
    )
    assert ok.status_code == 204

    allowed = client.get("/api/v1/projects", headers=_headers(token, str(org.id)))
    assert allowed.status_code == 200

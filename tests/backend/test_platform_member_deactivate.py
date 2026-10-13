from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_PLATFORM
from app.core.roles import Role
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _platform_admin(db_session) -> tuple[User, str]:
    user = User(
        email="plat-admin@lab.local",
        full_name="Platform Admin",
        hashed_password=hash_password("secret-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"platform_role": "SUPER_ADMIN", "platform_auth_version": 1},
        audience=AUD_PLATFORM,
    )
    return user, token


def test_deactivate_member_requires_reason(client: TestClient, db_session):
    admin, token = _platform_admin(db_session)
    org = Organization(name="Acme", slug="acme-deact", license_limit=5, license_status="active")
    db_session.add(org)
    db_session.flush()
    member_user = User(
        email="member@lab.local",
        full_name="Member",
        hashed_password=hash_password("secret-pass-123"),
        is_active=True,
    )
    db_session.add(member_user)
    db_session.flush()
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=member_user.id,
        role=Role.EDITOR.value,
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()

    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{membership.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert res.status_code == 422

    ok = client.post(
        f"/api/v1/admin/organizations/{org.id}/members/{membership.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
        json={"reason": "Offboarded per customer request"},
    )
    assert ok.status_code == 204, ok.text

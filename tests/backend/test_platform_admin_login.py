from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.organization import User


def test_login_accepts_local_domain_email(client: TestClient, db_session):
    user = User(
        email="admin@lab.local",
        full_name="Lab Admin",
        hashed_password=hash_password("secret-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@lab.local", "password": "secret-pass-123"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body.get("access_token")
    token = body["access_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": "null"},
    )
    assert me.status_code == 200, me.text
    me_body = me.json()
    assert me_body["is_platform_admin"] is True
    assert me_body["organization_id"] is None
    assert me_body.get("permissions")


def test_auth_me_platform_admin_without_org_header_skips_auto_membership(client: TestClient, db_session):
    from app.models.organization import Organization, OrganizationMembership

    user = User(
        email="admin3@lab.local",
        full_name="Lab Admin 3",
        hashed_password=hash_password("secret-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    org = Organization(name="Side Org", slug="side-org", license_limit=5, license_status="test")
    db_session.add(org)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role="ORG_ADMIN", is_active=True)
    )
    db_session.flush()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin3@lab.local", "password": "secret-pass-123"},
    )
    token = login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["organization_id"] is None


def test_auth_me_ignores_invalid_organization_header(client: TestClient, db_session):
    user = User(
        email="admin2@lab.local",
        full_name="Lab Admin 2",
        hashed_password=hash_password("secret-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin2@lab.local", "password": "secret-pass-123"},
    )
    token = login.json()["access_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": "not-a-valid-uuid"},
    )
    assert me.status_code == 200, me.text

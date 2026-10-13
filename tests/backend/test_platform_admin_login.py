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
    assert res.json().get("access_token")

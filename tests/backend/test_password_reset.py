from fastapi.testclient import TestClient

from app.core.jwt_audiences import AUD_EMPLOYEE
from app.core.security import create_access_token, hash_password, verify_password
from app.models.organization import Organization, OrganizationMembership, User


def test_forgot_password_same_response(client: TestClient, db_session):
    known = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.status_code == 200
    msg = known.json()["message"]
    user = User(email="exists@example.com", hashed_password=hash_password("old-password"), full_name="Exists")
    db_session.add(user)
    db_session.commit()
    again = client.post("/api/v1/auth/forgot-password", json={"email": "exists@example.com"})
    assert again.status_code == 200
    assert again.json()["message"] == msg


def test_reset_password_invalidates_sessions(client: TestClient, db_session, caplog):
    org = Organization(name="Reset Co", slug="reset-co", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(email="reset@example.com", hashed_password=hash_password("old-password"), full_name="Reset")
    db_session.add(user)
    db_session.flush()
    membership = OrganizationMembership(organization_id=org.id, user_id=user.id, role="EDITOR", auth_version=1)
    db_session.add(membership)
    db_session.commit()

    with caplog.at_level("INFO"):
        client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    reset_url = next(r.message for r in caplog.records if "Password reset link" in r.message)
    token = reset_url.split("token=")[-1].strip()

    old_token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": "EDITOR", "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    headers = {"Authorization": f"Bearer {old_token}", "X-Organization-Id": str(org.id)}
    assert client.get("/api/v1/projects", headers=headers).status_code == 200

    res = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "new-password-9"})
    assert res.status_code == 204

    db_session.refresh(user)
    db_session.refresh(membership)
    assert verify_password("new-password-9", user.hashed_password or "")
    assert membership.auth_version == 2
    assert client.get("/api/v1/projects", headers=headers).status_code == 401

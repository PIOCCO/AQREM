from fastapi.testclient import TestClient

from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def test_me_tenant_org_admin_has_admin_console_permission(client: TestClient, db_session):
    org = Organization(name="Acme", slug="acme-perm", license_limit=5)
    db_session.add(org)
    db_session.flush()
    admin = User(email="oa@example.com", hashed_password=hash_password("password"), full_name="OA")
    db_session.add(admin)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=admin.id, role=Role.ORG_ADMIN.value))
    db_session.flush()
    token = create_access_token(
        str(admin.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-org-admin"},
    )
    res = client.get("/api/v1/auth/me/tenant", headers=_headers(token, str(org.id)))
    assert res.status_code == 200
    body = res.json()
    assert "admin_console:access" in body["permissions"]


def test_me_tenant_editor_has_no_admin_permission(client: TestClient, db_session):
    org = Organization(name="Acme2", slug="acme-perm2", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(email="ed@example.com", hashed_password=hash_password("password"), full_name="Ed")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "aud": "aqrem-employee"},
    )
    res = client.get("/api/v1/auth/me/tenant", headers=_headers(token, str(org.id)))
    assert res.status_code == 200
    assert res.json()["permissions"] == []


def test_org_admin_api_rejects_employee_audience(client: TestClient, db_session):
    org = Organization(name="Acme3", slug="acme-perm3", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(email="oa2@example.com", hashed_password=hash_password("password"), full_name="OA2")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value))
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "aud": "aqrem-employee"},
    )
    res = client.get("/api/v1/org-admin/overview", headers=_headers(token, str(org.id)))
    assert res.status_code == 403

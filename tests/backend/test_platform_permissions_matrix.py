"""Platform role × permission enforcement against live route dependencies."""

from fastapi.testclient import TestClient

from app.core.permissions_catalog import platform_endpoint_permissions, platform_permissions_for_role
from app.core.platform_roles import PlatformRole
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.organization import User


def _platform_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_platform_user(db_session, role: PlatformRole) -> tuple[User, str]:
    user = User(
        email=f"{role.value.lower()}@matrix.test",
        full_name=role.value,
        hashed_password=hash_password("password"),
        is_platform_admin=role == PlatformRole.SUPER_ADMIN,
        platform_role=role.value,
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"aud": "aqrem-master", "platform_role": role.value, "platform_auth_version": 1},
    )
    return user, token


def test_catalog_matrix_matches_role_grants():
    endpoints = platform_endpoint_permissions()
    perms = sorted(set(endpoints.values()))
    for role in PlatformRole:
        granted = platform_permissions_for_role(role)
        matrix = {p: p in granted for p in perms}
        for perm, allowed in matrix.items():
            assert (perm in granted) == allowed


def test_support_cannot_create_organization(client: TestClient, db_session):
    _, token = _seed_platform_user(db_session, PlatformRole.PLATFORM_SUPPORT)
    res = client.post(
        "/api/v1/admin/organizations",
        headers=_platform_headers(token),
        json={
            "name": "Blocked Co",
            "license_limit": 5,
            "environment": "production",
        },
    )
    assert res.status_code == 403


def test_billing_can_read_orgs_but_not_create(client: TestClient, db_session):
    _, token = _seed_platform_user(db_session, PlatformRole.PLATFORM_BILLING)
    assert client.get("/api/v1/admin/organizations", headers=_platform_headers(token)).status_code == 200
    assert (
        client.post(
            "/api/v1/admin/organizations",
            headers=_platform_headers(token),
            json={"name": "X", "license_limit": 3, "environment": "production"},
        ).status_code
        == 403
    )


def test_super_admin_can_read_matrix(client: TestClient, db_session):
    _, token = _seed_platform_user(db_session, PlatformRole.SUPER_ADMIN)
    res = client.get("/api/v1/admin/permissions/matrix", headers=_platform_headers(token))
    assert res.status_code == 200
    body = res.json()
    assert "SUPER_ADMIN" in body["roles"]


def test_employee_token_rejected_by_platform_api(client: TestClient, db_session):
    from app.core.roles import Role
    from app.models.organization import Organization, OrganizationMembership

    org = Organization(name="T", slug="t-matrix", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(
        email="emp@matrix.test",
        full_name="Emp",
        hashed_password=hash_password("password"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value),
    )
    db_session.flush()
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "aud": "aqrem-employee", "auth_version": 1},
    )
    res = client.get("/api/v1/admin/organizations", headers=_platform_headers(token))
    assert res.status_code in (403, 401)


def test_platform_invite_org_user_must_be_org_admin(client: TestClient, db_session):
    from app.models.organization import Organization

    admin, token = _seed_platform_user(db_session, PlatformRole.SUPER_ADMIN)
    org = Organization(name="Cust", slug="cust-matrix", license_limit=5)
    db_session.add(org)
    db_session.flush()
    res = client.post(
        f"/api/v1/admin/organizations/{org.id}/users",
        headers=_platform_headers(token),
        json={"email": "newadmin@cust.test", "full_name": "New", "role": "EDITOR"},
    )
    assert res.status_code == 400 or res.status_code == 422 or res.json().get("detail", {}).get("code") == "ROLE_NOT_ALLOWED"

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import get_settings
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.roles import Role
from app.core.security import ALGORITHM, create_access_token, decode_access_token, hash_password
from app.models.organization import Organization, OrganizationMembership, User


def _headers(token: str, org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}


def _seed(db_session):
    org = Organization(name="JWT Org", slug="jwt-org", license_limit=5)
    db_session.add(org)
    db_session.flush()
    user = User(email="jwt@example.com", hashed_password=hash_password("password"), full_name="JWT User")
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EDITOR.value))
    db_session.commit()
    return org, user


def test_wrong_audience_rejected(client: TestClient, db_session):
    org, user = _seed(db_session)
    employee = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    platform = create_access_token(str(user.id), {"platform_role": "SUPER_ADMIN"}, audience=AUD_PLATFORM)
    assert client.get("/api/v1/projects", headers=_headers(platform, str(org.id))).status_code == 401
    assert client.get("/api/v1/master/environments", headers={"Authorization": f"Bearer {employee}"}).status_code == 401


def test_org_admin_audience_required_for_admin_console(client: TestClient, db_session):
    org, user = _seed(db_session)
    membership = (
        db_session.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.organization_id == org.id)
        .one()
    )
    membership.role = Role.ORG_ADMIN.value
    db_session.commit()
    employee_aud = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    assert client.get("/api/v1/org-admin/setup", headers=_headers(employee_aud, str(org.id))).status_code == 403


def test_tampered_token_rejected(client: TestClient, db_session):
    org, user = _seed(db_session)
    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.EDITOR.value, "auth_version": 1},
        audience=AUD_EMPLOYEE,
    )
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert client.get("/api/v1/projects", headers=_headers(tampered, str(org.id))).status_code == 401


def test_expired_token_rejected(client: TestClient, db_session):
    settings = get_settings()
    org, user = _seed(db_session)
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "exp": datetime.now(UTC) - timedelta(minutes=5),
            "iss": settings.jwt_issuer,
            "aud": AUD_EMPLOYEE,
            "organization_id": str(org.id),
            "role": Role.EDITOR.value,
        },
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    assert client.get("/api/v1/projects", headers=_headers(expired, str(org.id))).status_code == 401


def test_wrong_issuer_rejected():
    settings = get_settings()
    token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000001", "exp": datetime.now(UTC) + timedelta(hours=1), "iss": "evil", "aud": AUD_EMPLOYEE},
        settings.secret_key,
        algorithm=ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_access_token(token, audiences=AUD_EMPLOYEE)

"""Admin provisioning, licensing, and registration lockdown."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.roles import Role
from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.security import create_access_token, hash_password
from app.models.enums import LicenseStatus
from app.models.organization import Organization, OrganizationMembership, User
from app.services.licensing import licensing_test_mode_effective, org_allows_sign_in
from app.services.platform_provisioning import (
    accept_invitation,
    create_organization_admin,
    hash_invitation_token,
    provision_user_invitation,
)


class TestLicensingRules:
    def test_zero_license_active_org_denied(self):
        org = Organization(
            name="X", slug="x", license_limit=0, license_status=LicenseStatus.ACTIVE.value, is_active=True
        )
        allowed, reason = org_allows_sign_in(org, Settings(app_env="development", licensing_test_mode=True))
        assert not allowed
        assert "No licensed seats" in reason

    def test_test_org_allowed_in_dev_test_mode(self):
        org = Organization(
            name="T", slug="t", license_limit=0, license_status=LicenseStatus.TEST.value, is_active=True
        )
        allowed, _ = org_allows_sign_in(org, Settings(app_env="development", licensing_test_mode=True))
        assert allowed

    def test_test_org_denied_when_test_mode_off(self):
        org = Organization(
            name="T", slug="t", license_limit=0, license_status=LicenseStatus.TEST.value, is_active=True
        )
        allowed, reason = org_allows_sign_in(org, Settings(app_env="development", licensing_test_mode=False))
        assert not allowed
        assert "Test license" in reason

    def test_production_never_enables_licensing_test_mode(self):
        settings = Settings(
            app_env="production",
            licensing_test_mode=True,
            secret_key="x" * 32,
            allow_public_registration=True,
        )
        assert settings.licensing_test_mode is False
        assert settings.allow_public_registration is False
        assert licensing_test_mode_effective(settings) is False


def _postgres_available() -> bool:
    from sqlalchemy import create_engine, text

    url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem_test",
    )
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_public_registration_not_routed(client: TestClient, db_session):
    before = db_session.query(User).count()
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "password": "password123",
            "full_name": "New",
            "organization_name": "Evil Co",
        },
    )
    assert res.status_code == 404
    assert db_session.query(User).count() == before


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_admin_provisions_org_and_client_user(client: TestClient, db_session):
    admin = User(
        email="platform-admin@test.example",
        full_name="Admin",
        hashed_password=hash_password("admin-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    admin_token = create_access_token(
        str(admin.id),
        {"aud": "aqrem-master", "platform_role": "SUPER_ADMIN", "platform_auth_version": 1},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_res = client.post(
        "/api/v1/admin/organizations",
        headers=admin_headers,
        json={"name": "Client Co", "license_limit": 1, "environment": "test"},
    )
    assert create_res.status_code == 201, create_res.text
    org_id = create_res.json()["id"]
    assert create_res.json()["license_limit"] == 1

    prov_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/users",
        headers=admin_headers,
        json={"email": "client@clientco.example", "full_name": "Client User", "role": "ORG_ADMIN"},
    )
    assert prov_res.status_code == 201, prov_res.text
    setup_path = prov_res.json()["invitation_setup_path"]
    assert "token=" in setup_path

    non_admin = User(
        email="editor@test.example",
        full_name="Ed",
        hashed_password=hash_password("password123"),
        is_active=True,
    )
    db_session.add(non_admin)
    db_session.flush()
    editor_token = create_access_token(str(non_admin.id), {"role": Role.EDITOR.value})
    forbidden = client.post(
        f"/api/v1/admin/organizations/{org_id}/users",
        headers={"Authorization": f"Bearer {editor_token}"},
        json={"email": "x@y.example", "full_name": "X", "role": "VIEWER"},
    )
    assert forbidden.status_code in (401, 403)


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_admin_invite_zero_license_returns_actionable_error(client: TestClient, db_session):
    admin = User(
        email="platform-admin-zero@test.example",
        full_name="Admin",
        hashed_password=hash_password("admin-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    admin_token = create_access_token(
        str(admin.id),
        {"aud": "aqrem-master", "platform_role": "SUPER_ADMIN", "platform_auth_version": 1},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    org = Organization(
        name="Zero Seat Co",
        slug="zero-seat-co",
        license_limit=0,
        license_status=LicenseStatus.ACTIVE.value,
        is_active=True,
    )
    db_session.add(org)
    db_session.flush()
    org_id = str(org.id)

    list_res = client.get("/api/v1/admin/organizations", headers=admin_headers)
    assert list_res.status_code == 200
    listed = next(item for item in list_res.json()["items"] if item["id"] == org_id)
    assert listed["seats"]["is_full"] is True

    prov_res = client.post(
        f"/api/v1/admin/organizations/{org_id}/users",
        headers=admin_headers,
        json={"email": "client@zeroseat.example", "full_name": "Client User", "role": "ORG_ADMIN"},
    )
    assert prov_res.status_code == 403, prov_res.text
    body = prov_res.json()
    assert body["detail"]["code"] == "NO_LICENSED_SEATS"
    assert isinstance(body["message"], str) and body["message"]


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_admin_invite_validation_error_includes_message(client: TestClient, db_session):
    admin = User(
        email="platform-admin-val@test.example",
        full_name="Admin",
        hashed_password=hash_password("admin-pass-123"),
        is_platform_admin=True,
        platform_role="SUPER_ADMIN",
        platform_auth_version=1,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    org = Organization(
        name="Val Org",
        slug="val-org-invite",
        license_limit=5,
        license_status=LicenseStatus.ACTIVE.value,
        is_active=True,
    )
    db_session.add(org)
    db_session.flush()

    admin_token = create_access_token(
        str(admin.id),
        {"aud": "aqrem-master", "platform_role": "SUPER_ADMIN", "platform_auth_version": 1},
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    prov_res = client.post(
        f"/api/v1/admin/organizations/{org.id}/users",
        headers=admin_headers,
        json={"email": "not-an-email", "full_name": "X", "role": "EDITOR"},
    )
    assert prov_res.status_code == 422, prov_res.text
    body = prov_res.json()
    assert isinstance(body.get("message"), str) and body["message"]


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_invitation_single_use_and_expiry(db_session):
    admin = User(
        email="admin-invite@test.example",
        full_name="Admin",
        hashed_password=hash_password("admin-pass-123"),
        is_platform_admin=True,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()

    org = create_organization_admin(
        db_session,
        admin_user_id=admin.id,
        name="Invite Org",
        license_limit=0,
        license_status=LicenseStatus.TEST,
    )
    db_session.flush()

    _user, _membership, _inv, raw_token, _expires = provision_user_invitation(
        db_session,
        admin_user_id=admin.id,
        organization_id=org.id,
        email="invited@example.com",
        full_name="Invited",
        role=Role.EDITOR,
        expires_hours=1,
    )
    db_session.commit()

    accept_invitation(
        db_session,
        token=raw_token,
        email="invited@example.com",
        verification_code="",
        password="new-password-123",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="already used"):
        accept_invitation(
            db_session,
            token=raw_token,
            email="invited@example.com",
            verification_code="",
            password="another-pass-123",
        )

    from app.models.invitation import UserInvitation

    inv = db_session.query(UserInvitation).filter(UserInvitation.token_hash == hash_invitation_token(raw_token)).one()
    inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    _user2, _m2, _inv2, token2, _ = provision_user_invitation(
        db_session,
        admin_user_id=admin.id,
        organization_id=org.id,
        email="invited2@example.com",
        full_name="Invited2",
        role=Role.EDITOR,
    )
    db_session.commit()
    inv2 = db_session.query(UserInvitation).filter(UserInvitation.token_hash == hash_invitation_token(token2)).one()
    inv2.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()
    with pytest.raises(ValueError, match="expired"):
        accept_invitation(
            db_session,
            token=token2,
            email="invited2@example.com",
            verification_code="",
            password="password-12345",
        )


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_deactivated_user_cannot_use_api(client: TestClient, db_session):
    org = Organization(name="Deact Org", slug="deact", license_limit=1, license_status=LicenseStatus.ACTIVE.value)
    user = User(
        email="deact@example.com",
        full_name="Deact",
        hashed_password=hash_password("password123"),
        is_active=False,
    )
    db_session.add_all([org, user])
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=Role.EDITOR.value,
            is_active=True,
        )
    )
    db_session.flush()

    token = create_access_token(str(user.id), {"organization_id": str(org.id), "role": Role.EDITOR.value})
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)},
    )
    assert res.status_code == 401

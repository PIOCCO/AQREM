"""Test organizations must be hidden from platform admin when test mode is off."""

from app.core.security import create_access_token, hash_password
from app.models.enums import LicenseStatus
from app.models.organization import Organization, User


def test_hidden_test_org_directory_returns_404(client, db_session, monkeypatch):
    monkeypatch.setenv("LICENSING_TEST_MODE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()

    admin = User(
        email="platform@test.com",
        full_name="Admin",
        hashed_password=hash_password("password"),
        is_platform_admin=True,
    )
    test_org = Organization(
        name="Hidden Test",
        slug="hidden-test",
        license_limit=5,
        license_status=LicenseStatus.TEST.value,
        is_active=True,
    )
    db_session.add_all([admin, test_org])
    db_session.commit()

    token = create_access_token(str(admin.id), {"role": "PLATFORM_ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/admin/organizations/{test_org.id}/directory", headers=headers)
    assert res.status_code == 404

    get_settings.cache_clear()

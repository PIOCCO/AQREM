"""Platform admin bootstrap must not leak secrets or reset passwords in production."""

import logging

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.platform_roles import PlatformRole
from app.models.organization import User
from app.services.bootstrap import ensure_platform_admin


def test_bootstrap_skips_when_credentials_missing(db_session, caplog):
    caplog.set_level(logging.INFO)
    ensure_platform_admin(db_session)
    assert not any("password" in (r.message or "").lower() for r in caplog.records)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_bootstrap_creates_admin_without_logging_password(db_session, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("PLATFORM_ADMIN_EMAIL", "bootstrap@example.com")
    monkeypatch.setenv("PLATFORM_ADMIN_PASSWORD", "super-secret-bootstrap-pw")
    monkeypatch.setenv("PLATFORM_ADMIN_SYNC_PASSWORD", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    ensure_platform_admin(db_session)
    db_session.commit()
    user = db_session.execute(select(User).where(User.email == "bootstrap@example.com")).scalar_one()
    assert user.is_platform_admin
    assert user.platform_role == PlatformRole.SUPER_ADMIN.value
    assert user.hashed_password != "super-secret-bootstrap-pw"
    logged = " ".join(r.message for r in caplog.records)
    assert "super-secret-bootstrap-pw" not in logged


def test_production_settings_disable_password_sync(production_settings_env):
    prod = Settings(
        app_env="production",
        secret_key="x" * 32,
        platform_admin_sync_password=True,
    )
    assert prod.platform_admin_sync_password is False


def test_bootstrap_does_not_reset_existing_password_when_sync_disabled(db_session, monkeypatch, production_settings_env):
    from app.core.security import hash_password, verify_password

    email = "existing-admin@example.com"
    original_hash = hash_password("original-password")
    db_session.add(
        User(
            email=email,
            full_name="Existing",
            hashed_password=original_hash,
            is_platform_admin=True,
            platform_role=PlatformRole.SUPER_ADMIN.value,
            is_active=True,
        )
    )
    db_session.commit()

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "production-test-secret-key-32chars!!")
    monkeypatch.setenv("PLATFORM_ADMIN_EMAIL", email)
    monkeypatch.setenv("PLATFORM_ADMIN_PASSWORD", "new-env-password")
    from app.core.config import get_settings

    get_settings.cache_clear()
    ensure_platform_admin(db_session)
    db_session.commit()
    user = db_session.execute(select(User).where(User.email == email)).scalar_one()
    assert verify_password("original-password", user.hashed_password)
    assert not verify_password("new-env-password", user.hashed_password)

"""Ensure startup bootstrap does not create tenant organizations."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.organization import Organization, User
from app.services.bootstrap import ensure_platform_admin


def test_bootstrap_without_env_creates_no_users_or_orgs(db_session, monkeypatch):
    monkeypatch.delenv("PLATFORM_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("PLATFORM_ADMIN_PASSWORD", raising=False)
    before_orgs = db_session.scalar(select(func.count()).select_from(Organization)) or 0
    before_users = db_session.scalar(select(func.count()).select_from(User)) or 0

    ensure_platform_admin(db_session)

    after_orgs = db_session.scalar(select(func.count()).select_from(Organization)) or 0
    after_users = db_session.scalar(select(func.count()).select_from(User)) or 0
    assert after_orgs == before_orgs
    assert after_users == before_users


def test_bootstrap_does_not_create_organizations(db_session, monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_EMAIL", "only-admin@bootstrap.test")
    monkeypatch.setenv("PLATFORM_ADMIN_PASSWORD", "bootstrap-test-password-xyz")
    monkeypatch.setenv("PLATFORM_ADMIN_SYNC_PASSWORD", "false")

    ensure_platform_admin(db_session)
    db_session.commit()

    org_count = db_session.scalar(select(func.count()).select_from(Organization)) or 0
    assert org_count == 0

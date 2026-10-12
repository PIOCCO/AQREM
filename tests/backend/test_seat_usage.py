"""Seat usage: members + pending invitations."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from app.core.roles import Role
from app.models.enums import LicenseStatus
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.services.platform_provisioning import hash_invitation_token, provision_user_invitation
from app.services.licensing import LicenseDenied
from app.services.seat_usage import get_seat_usage


def _postgres_available() -> bool:
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
def test_seat_usage_counts_members_and_pending(db_session):
    org = Organization(
        name="Seats Co",
        slug="seats-co",
        license_limit=2,
        license_status=LicenseStatus.ACTIVE.value,
        is_active=True,
    )
    db_session.add(org)
    db_session.flush()
    user = User(email="a-seat@example.com", full_name="A", hashed_password="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=org.id, user_id=user.id, role=Role.EDITOR.value, is_active=True
        )
    )
    db_session.add(
        UserInvitation(
            organization_id=org.id,
            email="pending-seat@example.com",
            role=Role.VIEWER.value,
            token_hash=hash_invitation_token("tok-seat-test"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    db_session.flush()
    usage = get_seat_usage(db_session, org)
    assert usage.active_members == 1
    assert usage.pending_invitations == 1
    assert usage.seats_used == 2
    assert usage.is_full


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_invite_blocked_when_seats_full(db_session):
    admin = User(
        email="admin-seat-full@test.example",
        full_name="Admin",
        hashed_password="x",
        is_platform_admin=True,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    org = Organization(
        name="Full Co",
        slug="full-co",
        license_limit=1,
        license_status=LicenseStatus.ACTIVE.value,
        is_active=True,
    )
    db_session.add(org)
    db_session.flush()
    user = User(email="member@full.example", full_name="M", hashed_password="x", is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMembership(
            organization_id=org.id, user_id=user.id, role=Role.EDITOR.value, is_active=True
        )
    )
    db_session.flush()
    with pytest.raises(LicenseDenied):
        provision_user_invitation(
            db_session,
            admin_user_id=admin.id,
            organization_id=org.id,
            email="another@full.example",
            full_name="Another",
            role=Role.VIEWER,
        )

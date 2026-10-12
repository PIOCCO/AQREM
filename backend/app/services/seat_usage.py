"""Single source of truth: seats used = active members + pending invitations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.invitation import UserInvitation
from app.models.organization import OrganizationMembership


@dataclass(frozen=True)
class SeatUsage:
    active_members: int
    pending_invitations: int
    seats_used: int
    seats_limit: int

    @property
    def seats_available(self) -> int:
        return max(0, self.seats_limit - self.seats_used)

    @property
    def is_full(self) -> bool:
        if self.seats_limit <= 0:
            return False
        return self.seats_used >= self.seats_limit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def count_active_members(db: Session, organization_id: UUID) -> int:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .count()
    )


def count_pending_invitations(db: Session, organization_id: UUID) -> int:
    now = _utcnow()
    return (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .count()
    )


def get_seat_usage(db: Session, org) -> SeatUsage:
    limit = int(org.license_limit or 0)
    active = count_active_members(db, org.id)
    pending = count_pending_invitations(db, org.id)
    return SeatUsage(
        active_members=active,
        pending_invitations=pending,
        seats_used=active + pending,
        seats_limit=limit,
    )

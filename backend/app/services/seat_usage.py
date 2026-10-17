"""Single source of truth: seats used = active members + pending invitations + pending employee joins.

A seat is an *active* membership of an *active* user. Deactivated memberships and deactivated user
accounts do not count; neither do expired, revoked or used invitations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.roles import Role
from app.models.invitation import UserInvitation
from app.models.employee_join import EmployeeJoinPending
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
    from app.models.organization import User

    return (
        db.query(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True),
            User.is_active.is_(True),
        )
        .count()
    )


def count_pending_employee_joins(db: Session, organization_id: UUID) -> int:
    return (
        db.query(EmployeeJoinPending)
        .filter(
            EmployeeJoinPending.organization_id == organization_id,
            EmployeeJoinPending.status == "pending_approval",
        )
        .count()
    )


def count_pending_invitations(db: Session, organization_id: UUID) -> int:
    """Pending invites that do not yet occupy an active membership seat."""
    now = _utcnow()
    from app.models.organization import User

    pending = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == organization_id,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
            UserInvitation.expires_at > now,
        )
        .all()
    )
    extra = 0
    for inv in pending:
        if inv.invitation_kind == "org_admin" or inv.role == Role.ORG_ADMIN.value:
            extra += 1
            continue
        user = db.query(User).filter(User.email == inv.email.lower()).first()
        if user is None:
            extra += 1
            continue
        active = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.is_active.is_(True),
            )
            .first()
        )
        if active is None:
            extra += 1
    return extra


def get_seat_usage(db: Session, org) -> SeatUsage:
    limit = int(org.license_limit or 0)
    active = count_active_members(db, org.id)
    pending = count_pending_invitations(db, org.id)
    pending_employees = count_pending_employee_joins(db, org.id)
    return SeatUsage(
        active_members=active,
        pending_invitations=pending,
        seats_used=active + pending + pending_employees,
        seats_limit=limit,
    )

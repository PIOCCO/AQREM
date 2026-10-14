"""Organization membership removal and org-admin invariants."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.platform_access import resolve_platform_role
from app.core.roles import Role
from app.models.organization import OrganizationMembership, User
from app.services.platform_provisioning import revoke_pending_invitations_for_email


class MembershipRemoveError(ValueError):
    pass


def normalize_org_admin_singleton(db: Session, organization_id: UUID) -> None:
    """At most one ORG_ADMIN membership row; drop inactive duplicates, demote extra actives."""
    admins = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
        )
        .order_by(OrganizationMembership.is_active.desc(), OrganizationMembership.id.asc())
        .all()
    )
    if len(admins) <= 1:
        return
    keeper = admins[0]
    for extra in admins[1:]:
        if not extra.is_active:
            db.delete(extra)
        else:
            extra.role = Role.EDITOR.value
            extra.auth_version = int(extra.auth_version or 1) + 1


def purge_legacy_inactive_memberships(db: Session, organization_id: UUID) -> int:
    """Hard-delete inactive membership rows left by older soft-remove implementations."""
    stale = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(False),
        )
        .all()
    )
    removed = 0
    for membership in stale:
        db.delete(membership)
        removed += 1
    if removed:
        normalize_org_admin_singleton(db, organization_id)
    return removed


def count_active_org_admins(db: Session, organization_id: UUID) -> int:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
            OrganizationMembership.is_active.is_(True),
        )
        .count()
    )


def remove_organization_membership(
    db: Session,
    *,
    admin_user_id: UUID,
    membership: OrganizationMembership,
    reason: str | None = None,
    source: str = "platform_control_plane",
    audit_action: str = "organization_member_removed",
) -> None:
    """Hard-delete membership, revoke invites, invalidate sessions, optional orphan user deactivation."""
    if membership.user_id == admin_user_id:
        raise MembershipRemoveError("SELF_REMOVE_FORBIDDEN")

    user = db.get(User, membership.user_id)
    org_id = membership.organization_id
    membership_id = membership.id
    target_user_id = membership.user_id
    target_email = user.email if user else None
    target_role = membership.role

    skip_last_admin_guard = reason == "invitation_revoked"
    if (
        not skip_last_admin_guard
        and membership.role == Role.ORG_ADMIN.value
        and membership.is_active
        and count_active_org_admins(db, org_id) <= 1
    ):
        raise MembershipRemoveError("LAST_ORG_ADMIN")

    if user is not None and user.email and reason not in (
        "invitation_revoked",
        "organization_deleted",
    ):
        revoke_pending_invitations_for_email(
            db,
            admin_user_id=admin_user_id,
            organization_id=org_id,
            email=user.email,
        )

    membership = db.get(OrganizationMembership, membership_id)
    if membership is None:
        return

    membership.auth_version = int(membership.auth_version or 1) + 1
    db.flush()

    record_audit(
        db,
        organization_id=org_id,
        user_id=admin_user_id,
        action=audit_action,
        resource_type="organization_membership",
        resource_id=str(membership_id),
        metadata={
            "removed_user_id": str(target_user_id),
            "removed_email": target_email,
            "removed_role": target_role,
            "reason": reason,
            "source": source,
        },
    )

    db.delete(membership)
    db.flush()

    if user is not None and resolve_platform_role(user) is None:
        remaining = (
            db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == user.id)
            .count()
        )
        if remaining == 0:
            user.is_active = False

    normalize_org_admin_singleton(db, org_id)

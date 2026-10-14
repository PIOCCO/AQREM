"""Organization soft delete, retention, and tenant data purge."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.platform_access import resolve_platform_role
from app.core.platform_roles import PlatformRole
from app.models.client_admin import ClientDocument
from app.models.employee_join import EmployeeJoinLink, EmployeeJoinPending
from app.models.evidence import EvidenceItem, EvidenceItemVersion
from app.models.invitation import UserInvitation
from app.models.organization import Organization, OrganizationMembership, User
from app.models.source import Source
from app.services.invitations.employee_join import LINK_DISABLED, set_link_status
from app.services.platform_provisioning import revoke_pending_invitations_for_email, revoke_invitation

logger = logging.getLogger("aqrem.org_lifecycle")

ORG_DELETION_RETENTION_DAYS = 30


class OrganizationDeleteError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def assert_super_admin(user: User) -> None:
    if resolve_platform_role(user) != PlatformRole.SUPER_ADMIN:
        raise OrganizationDeleteError("SUPER_ADMIN_REQUIRED")


def schedule_organization_deletion(
    db: Session,
    *,
    admin: User,
    org: Organization,
    confirm_name: str,
) -> datetime:
    """Soft-delete organization; purge is scheduled after retention window."""
    assert_super_admin(admin)
    admin_user_id = admin.id
    if org.deleted_at is not None:
        raise OrganizationDeleteError("ALREADY_PENDING_DELETION")
    if confirm_name.strip() != org.name.strip():
        raise OrganizationDeleteError("CONFIRM_NAME_MISMATCH")

    now = _utcnow()
    purge_at = now + timedelta(days=ORG_DELETION_RETENTION_DAYS)

    record_audit(
        db,
        organization_id=None,
        user_id=admin_user_id,
        action="organization_deletion_scheduled",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={
            "organization_id": str(org.id),
            "organization_name": org.name,
            "organization_slug": org.slug,
            "environment": "test" if org.license_status == "test" else "production",
            "purge_scheduled_at": purge_at.isoformat(),
            "retention_days": ORG_DELETION_RETENTION_DAYS,
            "source": "platform_control_plane",
        },
    )

    _revoke_org_access(db, admin_user_id=admin_user_id, org=org)

    org.deleted_at = now
    org.purge_scheduled_at = purge_at
    org.is_active = False
    if org.slug and not org.slug.startswith("deleted-"):
        org.slug = f"deleted-{str(org.id).split('-')[0]}-{org.slug}"[:100]

    record_audit(
        db,
        organization_id=None,
        user_id=admin_user_id,
        action="organization_deleted",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={
            "organization_id": str(org.id),
            "organization_name": org.name,
            "deleted_at": now.isoformat(),
            "purge_scheduled_at": purge_at.isoformat(),
            "source": "platform_control_plane",
        },
    )
    return purge_at


def _revoke_org_access(db: Session, *, admin_user_id: UUID, org: Organization) -> None:
    now = _utcnow()
    invites = (
        db.query(UserInvitation)
        .filter(
            UserInvitation.organization_id == org.id,
            UserInvitation.used_at.is_(None),
            UserInvitation.revoked_at.is_(None),
        )
        .all()
    )
    for inv in invites:
        if inv.expires_at.tzinfo is None:
            exp = inv.expires_at.replace(tzinfo=timezone.utc)
        else:
            exp = inv.expires_at
        if exp > now:
            revoke_invitation(db, admin_user_id=admin_user_id, invitation=inv)

    for link in db.query(EmployeeJoinLink).filter(EmployeeJoinLink.organization_id == org.id).all():
        if link.status != LINK_DISABLED:
            set_link_status(db, admin_user_id=admin_user_id, link=link, status=LINK_DISABLED)

    memberships = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == org.id, OrganizationMembership.is_active.is_(True))
        .all()
    )
    for membership in memberships:
        membership.is_active = False
        membership.auth_version = int(membership.auth_version or 1) + 1
        user = db.get(User, membership.user_id)
        if user and user.email:
            revoke_pending_invitations_for_email(
                db,
                admin_user_id=admin_user_id,
                organization_id=org.id,
                email=user.email,
            )


def purge_organization_tenant_data(db: Session, organization_id: UUID) -> None:
    """Hard-delete tenant rows and storage references for an organization."""
    org = db.get(Organization, organization_id)
    if org is None:
        return

    docs = db.query(ClientDocument).filter(ClientDocument.organization_id == organization_id).all()
    blob_paths = [d.blob_path for d in docs if getattr(d, "blob_path", None)]

    db.execute(delete(EvidenceItemVersion).where(EvidenceItemVersion.organization_id == organization_id))
    db.execute(delete(EvidenceItem).where(EvidenceItem.organization_id == organization_id))
    db.execute(delete(Source).where(Source.organization_id == organization_id))
    db.execute(delete(ClientDocument).where(ClientDocument.organization_id == organization_id))
    db.execute(delete(EmployeeJoinPending).where(EmployeeJoinPending.organization_id == organization_id))

    try:
        from app.services.storage.factory import get_blob_storage

        storage = get_blob_storage()
        for path in blob_paths:
            try:
                storage.delete(path)
            except Exception:
                logger.exception("Failed to delete blob %s during org purge", path)
    except Exception:
        logger.exception("Storage backend unavailable during org purge for %s", organization_id)

    db.flush()


def purge_due_organizations(db: Session) -> int:
    """Hard-delete organizations whose retention window has elapsed."""
    now = _utcnow()
    due = (
        db.query(Organization)
        .filter(
            Organization.deleted_at.isnot(None),
            Organization.purge_scheduled_at.isnot(None),
            Organization.purge_scheduled_at <= now,
        )
        .all()
    )
    count = 0
    for org in due:
        purge_organization_tenant_data(db, org.id)
        db.delete(org)
        count += 1
    return count


def is_org_deleted(org: Organization) -> bool:
    return org.deleted_at is not None


def restore_organization(
    db: Session,
    *,
    admin: User,
    org: Organization,
) -> None:
    assert_super_admin(admin)
    if org.deleted_at is None:
        raise OrganizationDeleteError("NOT_PENDING_DELETION")
    org.deleted_at = None
    org.purge_scheduled_at = None
    org.is_active = True
    if org.slug.startswith("deleted-"):
        parts = org.slug.split("-", 2)
        if len(parts) >= 3:
            org.slug = parts[2][:100]
    record_audit(
        db,
        organization_id=None,
        user_id=admin.id,
        action="organization_deletion_restored",
        resource_type="organization",
        resource_id=str(org.id),
        metadata={"organization_id": str(org.id), "organization_name": org.name, "source": "platform_control_plane"},
    )


def purge_organization_now(
    db: Session,
    *,
    admin: User,
    org: Organization,
    confirm_name: str,
) -> None:
    assert_super_admin(admin)
    if confirm_name.strip() != org.name.strip():
        raise OrganizationDeleteError("CONFIRM_NAME_MISMATCH")
    if org.deleted_at is None:
        raise OrganizationDeleteError("NOT_PENDING_DELETION")
    org_id = org.id
    purge_organization_tenant_data(db, org_id)
    record_audit(
        db,
        organization_id=None,
        user_id=admin.id,
        action="organization_purged_immediately",
        resource_type="organization",
        resource_id=str(org_id),
        metadata={"organization_id": str(org_id), "organization_name": org.name, "source": "platform_control_plane"},
    )
    db.delete(org)


def run_scheduled_org_purges(db: Session) -> int:
    """Idempotent purge of organizations past retention. Returns count purged."""
    count = purge_due_organizations(db)
    if count:
        logger.info("Scheduled org purge completed: %s organization(s) permanently removed", count)
    return count

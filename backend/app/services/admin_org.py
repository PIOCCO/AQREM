from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.models.enums import LicenseStatus
from app.models.organization import Organization
from app.schemas.admin import AdminOrganizationResponse, SeatUsageResponse
from app.services.licensing import licensing_test_mode_effective
from app.services.seat_usage import SeatUsage, get_seat_usage


def org_environment(org: Organization) -> str:
    return "test" if org.license_status == LicenseStatus.TEST.value else "production"


def license_renews_at(org: Organization):
    if org.license_status != LicenseStatus.ACTIVE.value:
        return None
    if org.created_at is None:
        return None
    return org.created_at + timedelta(days=365)


def license_expires_at(org: Organization):
    if org.license_status != LicenseStatus.EXPIRED.value:
        return None
    if org.license_expires_at is not None:
        return org.license_expires_at
    return org.updated_at or org.created_at


def seat_usage_is_full(org: Organization, usage: SeatUsage) -> bool:
    if org.license_status == LicenseStatus.TEST.value and licensing_test_mode_effective():
        return False
    if usage.seats_limit <= 0:
        return True
    return usage.seats_used >= usage.seats_limit


def seat_usage_response(org: Organization, usage: SeatUsage) -> SeatUsageResponse:
    is_full = seat_usage_is_full(org, usage)
    seats_available = max(0, usage.seats_limit - usage.seats_used) if usage.seats_limit > 0 else 0
    return SeatUsageResponse(
        active_members=usage.active_members,
        pending_invitations=usage.pending_invitations,
        seats_used=usage.seats_used,
        seats_limit=usage.seats_limit,
        seats_available=seats_available,
        is_full=is_full,
    )


def org_to_admin_response(db: Session, org: Organization) -> AdminOrganizationResponse:
    usage = get_seat_usage(db, org)
    pending = getattr(org, "deleted_at", None) is not None
    return AdminOrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        license_limit=org.license_limit,
        license_status=org.license_status,
        environment=org_environment(org),
        is_active=org.is_active,
        owner_display_name=org.owner_display_name,
        created_at=org.created_at,
        license_renews_at=license_renews_at(org),
        license_expires_at=license_expires_at(org),
        deletion_status="pending_deletion" if pending else "active",
        purge_scheduled_at=getattr(org, "purge_scheduled_at", None) if pending else None,
        seats=seat_usage_response(org, usage),
    )


def org_status_bucket(org: Organization) -> str:
    if getattr(org, "deleted_at", None) is not None:
        return "pending_deletion"
    if org.license_status == LicenseStatus.TEST.value:
        return "test"
    if org.license_status == LicenseStatus.EXPIRED.value:
        return "expired"
    if org.license_status == LicenseStatus.SUSPENDED.value:
        return "suspended"
    return "active"


def organization_is_pending_deletion(org: Organization) -> bool:
    return getattr(org, "deleted_at", None) is not None


def organizations_base_query(db: Session) -> Query[Organization]:
    return db.query(Organization)


def organizations_excluding_pending_deletion(db: Session) -> Query[Organization]:
    """Default scope for operational org lists, seat usage, and get-by-id."""
    return organizations_base_query(db).filter(Organization.deleted_at.is_(None))


def organizations_pending_deletion_only(db: Session) -> Query[Organization]:
    return organizations_base_query(db).filter(Organization.deleted_at.isnot(None))


def filter_orgs_for_admin(orgs: list[Organization]) -> list[Organization]:
    visible = [o for o in orgs if getattr(o, "deleted_at", None) is None]
    if licensing_test_mode_effective():
        return visible
    return [o for o in visible if o.license_status != LicenseStatus.TEST.value]


def get_admin_visible_org(db: Session, organization_id: UUID) -> Organization | None:
    org = organizations_excluding_pending_deletion(db).filter(Organization.id == organization_id).first()
    if org is None:
        return None
    if org.license_status == LicenseStatus.TEST.value and not licensing_test_mode_effective():
        return None
    return org

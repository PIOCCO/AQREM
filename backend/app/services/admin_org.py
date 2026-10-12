from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

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


def seat_usage_response(usage: SeatUsage) -> SeatUsageResponse:
    return SeatUsageResponse(
        active_members=usage.active_members,
        pending_invitations=usage.pending_invitations,
        seats_used=usage.seats_used,
        seats_limit=usage.seats_limit,
        seats_available=usage.seats_available,
        is_full=usage.is_full,
    )


def org_to_admin_response(db: Session, org: Organization) -> AdminOrganizationResponse:
    usage = get_seat_usage(db, org)
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
        seats=seat_usage_response(usage),
    )


def org_status_bucket(org: Organization) -> str:
    if org.license_status == LicenseStatus.TEST.value:
        return "test"
    if org.license_status in {LicenseStatus.SUSPENDED.value, LicenseStatus.EXPIRED.value}:
        return "suspended"
    return "active"


def filter_orgs_for_admin(orgs: list[Organization]) -> list[Organization]:
    if licensing_test_mode_effective():
        return orgs
    return [o for o in orgs if o.license_status != LicenseStatus.TEST.value]

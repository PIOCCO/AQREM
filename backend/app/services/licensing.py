"""Organization seat licensing and test-mode rules."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.enums import LicenseStatus
from app.models.organization import Organization, OrganizationMembership


class LicenseDenied(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def licensing_test_mode_effective(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if settings.app_env == "production":
        return False
    return bool(settings.licensing_test_mode)


def count_active_seats(db: Session, organization_id: UUID) -> int:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .count()
    )


def org_allows_sign_in(org: Organization, settings: Settings | None = None) -> tuple[bool, str]:
    """Return whether members may authenticate against this organization."""
    settings = settings or get_settings()
    if not org.is_active:
        return False, "Organization is deactivated"

    status_value = org.license_status or LicenseStatus.ACTIVE.value
    if status_value == LicenseStatus.SUSPENDED.value:
        return False, "Organization license is suspended"

    if status_value == LicenseStatus.TEST.value:
        if not licensing_test_mode_effective(settings):
            return False, "Test license status is not enabled in this environment"
        # Test orgs may operate with license_limit=0 during licensed test mode only.
        return True, ""

    if org.license_limit <= 0:
        return False, "No licensed seats are allocated for this organization"

    return True, ""


def assert_can_add_seat(db: Session, org: Organization, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    allowed, reason = org_allows_sign_in(org, settings)
    if not allowed and org.license_status != LicenseStatus.TEST.value:
        raise LicenseDenied(reason)

    if org.license_status == LicenseStatus.TEST.value and licensing_test_mode_effective(settings):
        return

    seats = count_active_seats(db, org.id)
    if org.license_limit <= 0:
        raise LicenseDenied("license_limit is zero; increase seats or use a test organization in development")
    if seats >= org.license_limit:
        raise LicenseDenied("Organization has no remaining licensed seats")


def license_denied_http(exc: LicenseDenied) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail)

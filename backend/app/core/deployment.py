"""Deployment tier (shared vs dedicated) helpers.

shared    – default; many organizations, platform super-admin console fully enabled.
dedicated – one organization per environment (own containers + own PostgreSQL).
            The organization is created on first start; the first org admin is created
            through the one-time setup screen (/setup) protected by SETUP_TOKEN.
            The platform console is disabled, or read-only for support staff when
            DEDICATED_SUPPORT_ACCESS=true.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings

logger = logging.getLogger("aqrem")

PLATFORM_PREFIXES = ("/api/v1/admin", "/api/v1/master")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90] or "organization"


def get_dedicated_org(db: Session):
    from app.models.organization import Organization

    return (
        db.query(Organization)
        .filter(Organization.deleted_at.is_(None))
        .order_by(Organization.created_at.asc())
        .first()
    )


def ensure_dedicated_organization(db: Session, settings: Settings | None = None):
    """Create the single organization of a dedicated environment (idempotent)."""
    settings = settings or get_settings()
    if not settings.is_dedicated:
        return None
    from app.models.organization import Organization

    orgs = db.query(Organization).filter(Organization.deleted_at.is_(None)).all()
    if len(orgs) > 1:
        logger.error("DEPLOYMENT_MODE=dedicated but %s organizations exist; using the oldest", len(orgs))
    org = get_dedicated_org(db)
    if org is not None:
        return org
    name = (settings.dedicated_org_name or "").strip() or "Organization"
    org = Organization(
        name=name,
        slug=(settings.dedicated_org_slug or "").strip() or _slug(name),
        license_limit=0,
        is_active=True,
    )
    db.add(org)
    db.flush()
    from app.tenant_store.resolver import ensure_managed_config

    try:
        ensure_managed_config(db, org.id)
    except Exception:  # pragma: no cover - best effort; setup checklist shows it
        logger.exception("Could not create managed data-store config for dedicated org")
    logger.info("Dedicated organization created (id=%s)", org.id)
    return org


def dedicated_setup_required(db: Session) -> bool:
    from app.core.roles import Role
    from app.models.organization import OrganizationMembership

    org = get_dedicated_org(db)
    if org is None:
        return True
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.role == Role.ORG_ADMIN.value,
        )
        .first()
        is None
    )


def platform_route_allowed(path: str, method: str, settings: Settings | None = None) -> bool:
    """In dedicated mode the platform console is hidden (404) unless support read access is on."""
    settings = settings or get_settings()
    if not settings.is_dedicated:
        return True
    if not path.startswith(PLATFORM_PREFIXES):
        return True
    if path.startswith("/api/v1/admin/context"):
        return settings.dedicated_support_access
    if settings.dedicated_support_access and method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return True
    return False


def sync_license_to_org(db: Session, settings: Settings | None = None) -> None:
    """Mirror the offline license (seats/expiry) onto the dedicated org row for admin UIs."""
    settings = settings or get_settings()
    if not settings.is_dedicated:
        return
    from app.services.offline_license import VALID, load_license

    org = get_dedicated_org(db)
    if org is None:
        return
    res = load_license(settings)
    if res.state == VALID:
        org.license_limit = res.seats
        org.license_expires_at = res.expires_at
        org.license_status = "active"
    logger.log(logging.INFO if res.state == VALID else logging.ERROR, "License: %s %s", res.state, res.message)

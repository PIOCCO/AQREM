"""Operational endpoints: version, database test, diagnostics, fleet view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.platform_access import require_platform_permission
from app.models.organization import User
from app.services.system.health import app_version

router = APIRouter()          # mounted at /api/v1
platform_router = APIRouter()  # mounted at /api/v1/admin/system (platform console)


@router.get("/version")
def version() -> dict:
    """Unauthenticated: version + deployment metadata for the fleet view (no secrets)."""
    s = get_settings()
    from app.db.migrate import LATEST_VERSION

    return {
        "version": app_version(s),
        "deployment_mode": s.deployment_mode,
        "environment": s.environment_name or s.app_env,
        "schema_version": LATEST_VERSION,
    }


def _database_check_payload() -> dict:
    from app.db.session import engine
    from app.services.system.db_check import run_database_checks

    s = get_settings()
    out = {"app": run_database_checks(s.database_url, role="app", require_tls=s.tls_required_for_db,
                                      engine=engine).to_dict()}
    if (s.migration_database_url or "").strip():
        out["migration"] = run_database_checks(s.migration_database_url, role="migration",
                                               require_tls=s.tls_required_for_db).to_dict()
    return out


@platform_router.get("/database-check")
def platform_database_check(_: User = Depends(require_platform_permission("deployment:read"))) -> dict:
    return _database_check_payload()


@platform_router.get("/health")
def platform_health(_: User = Depends(require_platform_permission("deployment:read"))) -> dict:
    from app.services.system.health import dependency_report

    return dependency_report(use_cache=False)


def require_dedicated() -> None:
    if not get_settings().is_dedicated:
        # In the shared tier the database belongs to the platform, not to one org admin.
        raise HTTPException(status_code=404, detail="Only available in dedicated environments")

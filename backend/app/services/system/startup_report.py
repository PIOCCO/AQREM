"""One log line per dependency at startup (no secrets)."""

from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger("aqrem.startup")


def log_startup_report(settings: Settings) -> dict:
    from app.services.system.health import dependency_report

    try:
        report = dependency_report(settings, use_cache=False)
    except Exception:
        logger.exception("Startup dependency report failed")
        return {}
    logger.info(
        "Startup: version=%s mode=%s environment=%s status=%s",
        report["version"], report["deployment_mode"], report["environment"], report["status"],
    )
    for name, dep in report["dependencies"].items():
        level = logging.INFO if dep.get("status") in {"ok", "not_configured", "configured", "shared_mode", "valid"} else logging.WARNING
        logger.log(level, "Startup dependency %s: %s", name, {k: v for k, v in dep.items()})
    if settings.app_env == "production" and not settings.is_dedicated and not (settings.tenant_database_url or "").strip():
        logger.warning(
            "Shared production without TENANT_DATABASE_URL (Key Vault secret tenant-database-url): tenant "
            "sessions use the control-plane role, which can read identity tables of every org. "
            "See docs/sql/app_role.sql (aqrem_tenant)."
        )
    if settings.app_env == "production" or settings.is_dedicated:
        from app.services.system.db_check import run_database_checks
        from app.db.session import engine

        db = run_database_checks(settings.database_url, role="app", require_tls=settings.tls_required_for_db, engine=engine)
        for c in db.checks:
            logger.log(logging.ERROR if c.status == "fail" else (logging.WARNING if c.status == "warn" else logging.INFO),
                       "Database check %s: %s - %s", c.name, c.status, c.message)
    return report

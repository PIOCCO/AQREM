"""Health checks when org admin confirms tenant PostgreSQL setup."""

from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy import text

from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.masking import mask_message
from app.tenant_store.migrations import assert_schema_compatible
from app.tenant_store.pool import tenant_pool_manager
from app.tenant_store.preflight import run_preflight
from app.tenant_store.resolver import CUSTOMER_POSTGRES, MANAGED_COLOCATED, build_database_url
from app.tenant_store.secrets import SecretStore, default_secret_store


def validate_managed_colocated(organization_id: UUID) -> tuple[bool, str, int | None]:
    """Verify AQREM-managed PostgreSQL is reachable and tenant schema is compatible."""
    probe = TenantDataStoreConfig(
        organization_id=organization_id,
        storage_mode=MANAGED_COLOCATED,
        connection_method="managed",
        status="active",
    )
    url = build_database_url(probe, default_secret_store())
    tenant_key = f"probe-managed:{organization_id}"
    started = time.monotonic()
    session = tenant_pool_manager.session_factory(tenant_key, url)()
    try:
        session.execute(text("SELECT 1"))
        assert_schema_compatible(session)
        latency_ms = int((time.monotonic() - started) * 1000)
        return True, "AQREM-managed PostgreSQL is reachable and schema-compatible.", latency_ms
    except Exception as exc:
        return False, mask_message(str(exc)), None
    finally:
        session.close()


def refresh_config_health(
    cfg: TenantDataStoreConfig,
    *,
    secrets: SecretStore | None = None,
) -> tuple[bool, str, int | None]:
    """Re-run health check for the active stored configuration."""
    secrets = secrets or default_secret_store()
    if cfg.storage_mode == MANAGED_COLOCATED:
        return validate_managed_colocated(cfg.organization_id)
    if cfg.storage_mode != CUSTOMER_POSTGRES:
        return False, "Storage mode is not configured.", None
    if not cfg.host or not cfg.database_name or not cfg.username or not cfg.secret_reference:
        return False, "Customer database connection is incomplete.", None
    password = secrets.get(cfg.secret_reference)
    if not password:
        return False, "Database credentials are missing. Re-enter credentials and save.", None
    report = run_preflight(
        host=cfg.host,
        port=cfg.port,
        database_name=cfg.database_name,
        username=cfg.username,
        password=password,
        ssl_mode=cfg.ssl_mode,
        connection_method=cfg.connection_method,
        schema_name=cfg.schema_name,
    )
    if not report.ok:
        detail = next((c.detail for c in report.checks if c.status == "fail"), "Connection check failed.")
        return False, detail, report.latency_ms
    return True, "Connection and schema checks passed.", report.latency_ms

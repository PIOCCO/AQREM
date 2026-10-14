"""Health checks when org admin confirms tenant PostgreSQL setup."""

from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.masking import mask_message
from app.tenant_store.migrations import assert_schema_compatible
from app.tenant_store.pool import tenant_pool_manager
from app.tenant_store.resolver import MANAGED_COLOCATED, build_database_url
from app.tenant_store.secrets import default_secret_store


def validate_managed_colocated(control_db: Session, organization_id: UUID) -> tuple[bool, str, int | None]:
    """Verify AQREM-managed PostgreSQL is reachable and tenant schema is compatible."""
    settings = get_settings()
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

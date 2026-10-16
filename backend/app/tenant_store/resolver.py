"""Resolve tenant data store connections from control-plane configuration."""

from __future__ import annotations

import logging
from collections.abc import Generator
from urllib.parse import quote_plus
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tenant_data_store import TenantDataStoreConfig
from app.tenant_store.exceptions import TenantStoreUnavailable
from app.tenant_store.migrations import assert_schema_compatible
from app.tenant_store.pool import tenant_pool_manager
from app.tenant_store.secrets import SecretStore, default_secret_store
from app.tenant_store.ssrf import validate_host_port

logger = logging.getLogger("aqrem.tenant_resolver")

MANAGED_COLOCATED = "managed_colocated"
CUSTOMER_POSTGRES = "customer_postgres"


def default_secret_reference(organization_id: UUID) -> str:
    return f"AQREM_TENANT_DB_SECRET_{organization_id.hex}"


def get_tenant_store_config(control_db: Session, organization_id: UUID) -> TenantDataStoreConfig | None:
    return (
        control_db.query(TenantDataStoreConfig)
        .filter(TenantDataStoreConfig.organization_id == organization_id)
        .first()
    )


def ensure_managed_config(control_db: Session, organization_id: UUID) -> TenantDataStoreConfig:
    from datetime import UTC, datetime

    from app.core.config import is_local_prod_stack
    row = (
        control_db.query(TenantDataStoreConfig)
        .filter(TenantDataStoreConfig.organization_id == organization_id)
        .first()
    )
    if row:
        return row
    row = TenantDataStoreConfig(
        organization_id=organization_id,
        storage_mode=MANAGED_COLOCATED,
        connection_method="managed",
        status="active",
        schema_version=1,
        setup_validated_at=datetime.now(UTC) if is_local_prod_stack() else None,
    )
    control_db.add(row)
    control_db.flush()
    return row


def build_database_url(config: TenantDataStoreConfig, secrets: SecretStore) -> str:
    settings = get_settings()
    if config.storage_mode == MANAGED_COLOCATED:
        return (settings.tenant_database_url or "").strip() or settings.database_url

    if config.storage_mode != CUSTOMER_POSTGRES:
        raise TenantStoreUnavailable("Storage mode is not configured.")

    if config.paused:
        raise TenantStoreUnavailable(
            "Your company's data store is paused. Your administrator can re-enable it in Data storage."
        )

    if not config.host or not config.database_name or not config.username or not config.secret_reference:
        raise TenantStoreUnavailable("Customer database connection is incomplete. Finish setup in Data storage.")

    allow_private = config.connection_method in {"private_link", "vpn", "secure_connector", "customer_deployed"}
    validate_host_port(config.host, config.port, allow_private=allow_private)

    password = secrets.get(config.secret_reference)
    if not password:
        raise TenantStoreUnavailable("Database credentials are missing. Re-enter credentials in Data storage.")

    sslmode = config.ssl_mode or "verify-full"
    if sslmode in {"disable", "allow", "prefer"}:
        raise TenantStoreUnavailable("Unencrypted database connections are not allowed.")

    user = quote_plus(config.username)
    pwd = quote_plus(password)
    host = config.host
    port = config.port or 5432
    db = quote_plus(config.database_name)
    return f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}?sslmode={quote_plus(sslmode)}"


def open_tenant_session(
    control_db: Session,
    organization_id: UUID,
    *,
    secrets: SecretStore | None = None,
):
    secrets = secrets or default_secret_store()
    config = ensure_managed_config(control_db, organization_id)
    tenant_key = str(organization_id)
    url = build_database_url(config, secrets)
    factory = tenant_pool_manager.session_factory(tenant_key, url)
    session = factory()
    from app.db.rls import scope_session_to_org

    # RLS: every transaction of this session runs with SET LOCAL app.current_org = <org>.
    scope_session_to_org(session, organization_id)
    try:
        assert_schema_compatible(session)
        tenant_pool_manager.record_success(tenant_key)
        return session
    except Exception:
        session.close()
        tenant_pool_manager.record_failure(tenant_key)
        raise


def tenant_db_session(
    control_db: Session,
    organization_id: UUID,
    secrets: SecretStore | None = None,
) -> Generator:
    session = open_tenant_session(control_db, organization_id, secrets=secrets)
    try:
        yield session
    finally:
        session.close()

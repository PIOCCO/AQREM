"""Per-tenant schema migrations (forward-only, advisory lock)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.tenant_base import TenantBase
from app.tenant_store.exceptions import TenantSchemaMismatch

logger = logging.getLogger("aqrem.tenant_migrations")

CURRENT_SCHEMA_VERSION = 1
ADVISORY_LOCK_KEY = 915_001_337


@dataclass
class MigrationResult:
    status: str
    from_version: int
    to_version: int
    detail: str


def _ensure_migrations_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )


def read_schema_version(session: Session) -> int:
    exists = session.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = 'schema_migrations'
            LIMIT 1
            """
        )
    ).scalar()
    if not exists:
        return 0
    row = session.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar()
    return int(row or 0)


def assert_schema_compatible(session: Session) -> None:
    version = read_schema_version(session)
    if version > CURRENT_SCHEMA_VERSION:
        raise TenantSchemaMismatch(
            f"Tenant database schema version {version} is newer than this application ({CURRENT_SCHEMA_VERSION})."
        )
    if version < CURRENT_SCHEMA_VERSION - 1:
        raise TenantSchemaMismatch(
            f"Tenant database schema version {version} is too old. Run migrations from the admin console."
        )


def migrate_tenant_engine(engine: Engine, *, dry_run: bool = False) -> MigrationResult:
    _ensure_migrations_table(engine)
    with engine.connect() as conn:
        locked = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}).scalar()
        if not locked:
            return MigrationResult("locked", 0, 0, "Another migration is already running for this database.")
        try:
            current = conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar() or 0
            current = int(current)
            if current >= CURRENT_SCHEMA_VERSION:
                return MigrationResult("up_to_date", current, current, "Schema is up to date.")

            if dry_run:
                return MigrationResult(
                    "dry_run",
                    current,
                    CURRENT_SCHEMA_VERSION,
                    f"Would upgrade from {current} to {CURRENT_SCHEMA_VERSION}.",
                )

            if current == 0:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                TenantBase.metadata.create_all(bind=conn)
                conn.execute(
                    text("INSERT INTO schema_migrations (version) VALUES (:v) ON CONFLICT DO NOTHING"),
                    {"v": CURRENT_SCHEMA_VERSION},
                )
                conn.commit()
                return MigrationResult("migrated", 0, CURRENT_SCHEMA_VERSION, "Initial tenant schema created.")

            return MigrationResult("failed", current, current, "Unsupported migration step — contact support.")
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})

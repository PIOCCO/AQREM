"""Versioned, forward-only, non-destructive control/shared schema migrations.

Run at API startup (RUN_MIGRATIONS_ON_STARTUP=true, default) or as a separate job:

    python -m app.db.migrate            # apply pending
    python -m app.db.migrate --status   # show applied/pending, exit 1 if pending

Uses MIGRATION_DATABASE_URL (owner role) when set, otherwise DATABASE_URL.
A PostgreSQL advisory lock serialises concurrent runners (several replicas starting).

Rules for adding a migration (enforced by tests/backend/test_migrations_policy.py):
* append a new Migration with the next integer version; never edit or reorder old ones;
* additive only (CREATE ... IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS);
  no DROP TABLE / DROP COLUMN / TRUNCATE — removals are a two-release process documented in
  docs/migrations.md with rollback notes.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("aqrem.migrate")

LOCK_KEY = 915_001_001
TABLE = "aqrem_schema_versions"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[Connection], None]
    rollback_note: str


def _m1_baseline(conn: Connection) -> None:
    from app.db.control_base import ControlBase
    from app.db.schema_patches import apply_schema_patches
    from app.db.tenant_base import TenantBase
    import app.models  # noqa: F401

    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    ControlBase.metadata.create_all(bind=conn)
    TenantBase.metadata.create_all(bind=conn)
    apply_schema_patches(conn)


def _m2_indexes(conn: Connection) -> None:
    # Composite index for org-scoped retrieval / listing (additive).
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_evidence_items_org_source ON evidence_items (organization_id, source_id)"
    ))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_client_documents_org_created ON client_documents (organization_id, created_at)"
    ))


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "baseline (models + idempotent schema patches)", _m1_baseline,
              "Baseline; rollback = restore the pre-upgrade database backup."),
    Migration(2, "org-scoped composite indexes", _m2_indexes,
              "Safe to keep on rollback; to remove: DROP INDEX IF EXISTS ix_evidence_items_org_source, "
              "ix_client_documents_org_created."),
)

LATEST_VERSION = MIGRATIONS[-1].version


def _ensure_table(conn: Connection) -> None:
    conn.execute(text(
        f"CREATE TABLE IF NOT EXISTS {TABLE} (version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), app_version TEXT)"
    ))


def applied_versions(conn: Connection) -> set[int]:
    exists = conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": TABLE}).scalar()
    if not exists:
        return set()
    return {int(r[0]) for r in conn.execute(text(f"SELECT version FROM {TABLE}"))}


def pending(engine: Engine) -> list[Migration]:
    with engine.connect() as conn:
        done = applied_versions(conn)
    return [m for m in MIGRATIONS if m.version not in done]


def run_migrations(engine: Engine, *, app_version: str = "") -> list[int]:
    applied: list[int] = []
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
        _ensure_table(conn)
        done = applied_versions(conn)
        for m in MIGRATIONS:
            if m.version in done:
                continue
            logger.info("Applying migration %s: %s", m.version, m.name)
            with conn.begin_nested():
                m.apply(conn)
                conn.execute(
                    text(f"INSERT INTO {TABLE} (version, name, app_version) VALUES (:v, :n, :a)"),
                    {"v": m.version, "n": m.name, "a": app_version or None},
                )
            applied.append(m.version)
    if applied:
        logger.info("Migrations applied: %s", applied)
    return applied


def migration_engine() -> Engine:
    from app.core.config import get_settings

    s = get_settings()
    url = (s.migration_database_url or "").strip() or s.database_url
    return create_engine(url, pool_pre_ping=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AQREM schema migrations")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    from app.core.config import get_settings

    eng = migration_engine()
    try:
        if args.status:
            todo = pending(eng)
            for m in MIGRATIONS:
                print(f"{m.version:>4}  {'pending' if m in todo else 'applied'}  {m.name}")
            return 1 if todo else 0
        run_migrations(eng, app_version=get_settings().app_version)
        return 0
    finally:
        eng.dispose()


if __name__ == "__main__":
    sys.exit(main())

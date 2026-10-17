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
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("aqrem.migrate")

LOCK_KEY = 915_001_001
TABLE = "aqrem_schema_versions"
GUARD_TABLE = "aqrem_schema_guard"


class ImageTooOldError(RuntimeError):
    """The database was migrated by a newer image whose changes this image cannot honour."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[Connection], None]
    rollback_note: str
    # Set when images WITHOUT this migration must not run on a database that has it (e.g. RLS: an old
    # image would see no rows; setup_tokens: an old image would lose the one-time token guarantee).
    # Recorded in aqrem_schema_guard; images check it at startup (check_image_compatible).
    requires_image_feature: str | None = None


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


def _m3_row_level_security(conn: Connection) -> None:
    from app.db.rls import apply_rls

    # org_id indexes RLS relies on (most already exist via index=True; these are additive no-ops then).
    for t in ("evidence_items", "evidence_item_versions", "client_documents", "sources", "source_sync_jobs",
              "audit_events", "answers", "questions", "questionnaires", "organization_memberships"):
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_rls_{t}_org ON {t} (organization_id)"))
    apply_rls(conn)


def _m4_chat_strictness(conn: Connection) -> None:
    conn.execute(text(
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS chat_strictness VARCHAR(16) NOT NULL DEFAULT 'balanced'"
    ))


def _m5_setup_tokens(conn: Connection) -> None:
    from app.models.setup_token import SetupAttempt, SetupToken

    SetupToken.__table__.create(bind=conn, checkfirst=True)
    SetupAttempt.__table__.create(bind=conn, checkfirst=True)
    # Control-plane only: the tenant/support roles have no business reading setup state.
    conn.execute(text("""
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['aqrem_tenant', 'aqrem_support'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON setup_tokens, setup_attempts FROM %I', r);
    END IF;
  END LOOP;
END $$;
"""))


def _m6_schema_guard(conn: Connection) -> None:
    conn.execute(text(
        f"CREATE TABLE IF NOT EXISTS {GUARD_TABLE} (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
    ))
    conn.execute(text(f"REVOKE ALL ON {GUARD_TABLE} FROM PUBLIC"))
    conn.execute(text(f"GRANT SELECT ON {GUARD_TABLE} TO PUBLIC"))
    # Runtime roles may read the marker but never lower it (only the migration/owner role writes).
    conn.execute(text(f"""
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['aqrem_app', 'aqrem_tenant', 'aqrem_support'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON {GUARD_TABLE} FROM %I', r);
      EXECUTE format('GRANT SELECT ON {GUARD_TABLE} TO %I', r);
    END IF;
  END LOOP;
END $$;
"""))


# Tables whose runtime-role privileges are narrower than the blanket DML grant of ensure_app_role.
_RESTRICTED_FOR_RUNTIME = {
    GUARD_TABLE: "INSERT, UPDATE, DELETE, TRUNCATE",       # marker: read-only for runtime roles
    "license_runtime_state": "DELETE, TRUNCATE",          # evidence: never erased by the app
}


def restrict_runtime_role(conn: Connection, role: str) -> None:
    """Re-apply per-table restrictions after a blanket GRANT ... ON ALL TABLES (idempotent)."""
    for table, privs in _RESTRICTED_FOR_RUNTIME.items():
        if conn.execute(text("SELECT to_regclass(:t)"), {"t": table}).scalar() is not None:
            conn.execute(text(f'REVOKE {privs} ON {table} FROM "{role}"'))


def _m7_license_runtime_state(conn: Connection) -> None:
    from app.models.license_state import LicenseRuntimeState

    LicenseRuntimeState.__table__.create(bind=conn, checkfirst=True)
    # The app role keeps the row current (no DELETE: rollback/grace evidence is never erased by the app).
    conn.execute(text("""
DO $$
DECLARE r text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aqrem_app') THEN
    REVOKE ALL ON license_runtime_state FROM aqrem_app;
    GRANT SELECT, INSERT, UPDATE ON license_runtime_state TO aqrem_app;
  END IF;
  FOREACH r IN ARRAY ARRAY['aqrem_tenant', 'aqrem_support'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON license_runtime_state FROM %I', r);
    END IF;
  END LOOP;
END $$;
"""))


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "baseline (models + idempotent schema patches)", _m1_baseline,
              "Baseline; rollback = restore the pre-upgrade database backup."),
    Migration(2, "org-scoped composite indexes", _m2_indexes,
              "Safe to keep on rollback; to remove: DROP INDEX IF EXISTS ix_evidence_items_org_source, "
              "ix_client_documents_org_created."),
    Migration(3, "row-level security (org isolation, fail closed)", _m3_row_level_security,
              "No data change. Emergency rollback (per table, as owner): ALTER TABLE <t> NO FORCE ROW LEVEL "
              "SECURITY; ALTER TABLE <t> DISABLE ROW LEVEL SECURITY; policies may stay. See docs/migrations.md.",
              requires_image_feature="rls_org_isolation"),
    Migration(4, "organizations.chat_strictness (chat guardrails)", _m4_chat_strictness,
              "Additive column with default; older images ignore it. Optional removal (two-release rule): "
              "ALTER TABLE organizations DROP COLUMN chat_strictness."),
    Migration(5, "setup_tokens + setup_attempts (one-time dedicated setup)", _m5_setup_tokens,
              "Older images ignore both tables (they read SETUP_TOKEN directly, i.e. lose the one-time/expiry "
              "guarantees). Optional cleanup after rolling back: DROP TABLE setup_attempts, setup_tokens "
              "(separately reviewed).",
              requires_image_feature="setup_tokens_v1"),
    Migration(6, "aqrem_schema_guard (image/schema compatibility marker)", _m6_schema_guard,
              "Images built before this migration ignore the table (they cannot enforce it). Rolling back to "
              "such an image requires the manual check in docs/migrations.md. Do not drop the table."),
    Migration(7, "license_runtime_state (clock-rollback + license grace tracking)", _m7_license_runtime_state,
              "Older images ignore the table (they apply their own, stricter license rules). Do not drop it: "
              "it holds the clock-rollback and grace-period evidence."),
)

LATEST_VERSION = MIGRATIONS[-1].version


SUPPORTED_FEATURES = frozenset(m.requires_image_feature for m in MIGRATIONS if m.requires_image_feature)


def _guard_exists(conn: Connection) -> bool:
    return bool(conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": GUARD_TABLE}).scalar())


def read_guard(conn: Connection) -> dict[str, str]:
    if not _guard_exists(conn):
        return {}
    return {str(k): str(v) for k, v in conn.execute(text(f"SELECT key, value FROM {GUARD_TABLE}"))}


def check_image_compatible(conn: Connection) -> None:
    """Raise ImageTooOldError when the database requires a newer image than this one."""
    guard = read_guard(conn)
    if not guard:
        return
    try:
        min_schema = int(guard.get("min_image_schema", "0") or 0)
    except ValueError:
        min_schema = 10**9  # unreadable marker: fail closed
    required = {f for f in (guard.get("required_features", "") or "").split(",") if f}
    missing = sorted(required - SUPPORTED_FEATURES)
    if min_schema > LATEST_VERSION or missing:
        raise ImageTooOldError(
            f"This image (schema {LATEST_VERSION}) is older than the database requires "
            f"(min_image_schema={min_schema}, missing features={missing or '-'}). Refusing to start: running it "
            "could bypass row-level security or one-time setup. Deploy an image at or above the database's "
            "schema, or follow 'Rolling back below a guarded migration' in docs/migrations.md."
        )


def _write_guard(conn: Connection, done: set[int]) -> None:
    if not _guard_exists(conn):
        return
    current = read_guard(conn)
    flagged = [m for m in MIGRATIONS if m.version in done and m.requires_image_feature]
    min_schema = max([m.version for m in flagged], default=0)
    try:
        min_schema = max(min_schema, int(current.get("min_image_schema", "0") or 0))  # never lowered
    except ValueError:
        pass
    feats = {m.requires_image_feature for m in flagged} | {
        f for f in (current.get("required_features", "") or "").split(",") if f}
    for key, value in (("min_image_schema", str(min_schema)), ("required_features", ",".join(sorted(feats)))):
        conn.execute(
            text(f"INSERT INTO {GUARD_TABLE} (key, value) VALUES (:k, :v) "
                 "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()"),
            {"k": key, "v": value},
        )


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
        check_image_compatible(conn)  # never let an older migrator touch a newer database
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
        _write_guard(conn, applied_versions(conn))
    if applied:
        logger.info("Migrations applied: %s", applied)
    return applied


def ensure_app_role(engine: Engine, role: str, password: str) -> None:
    """Create/refresh the least-privilege runtime role (idempotent). Mirrors docs/sql/app_role.sql."""
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role or ""):
        raise ValueError("APP_DB_ROLE must be a simple lowercase identifier")
    try:
        _ensure_app_role(engine, role, password)
    except Exception as exc:
        # Never surface SQL parameters (they contain the password).
        raise RuntimeError(f"Could not ensure app role {role}: {type(exc).__name__}") from None
    logger.info("Least-privilege app role %s ensured", role)


def _ensure_app_role(engine: Engine, role: str, password: str) -> None:
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
        # Password is passed as a bound literal via format() server-side; never logged.
        stmt = "CREATE ROLE %I LOGIN PASSWORD %L" if not exists else "ALTER ROLE %I LOGIN PASSWORD %L"
        sql = conn.execute(
            text("SELECT format(CAST(:f AS text), CAST(:r AS text), CAST(:p AS text))"),
            {"f": stmt, "r": role, "p": password},
        ).scalar()
        conn.execute(text(sql))
        db = conn.execute(text("SELECT current_database()")).scalar()
        for q in (
            f'GRANT CONNECT, TEMPORARY ON DATABASE "{db}" TO {role}',
            f"GRANT USAGE ON SCHEMA public TO {role}",
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}",
            f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {role}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {role}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {role}",
            # RLS: control-plane group (cross-org on identity tables only); never BYPASSRLS, never owner.
            f"GRANT aqrem_rls_control TO {role}",
        ):
            conn.execute(text(q))
        # The blanket grant above re-opened write access to the schema guard / license evidence.
        restrict_runtime_role(conn, role)
        bad = conn.execute(
            text("SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).scalar()
        if bad:
            raise ValueError("app role must not be SUPERUSER or BYPASSRLS")


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
        role = (os.environ.get("APP_DB_ROLE") or "").strip()
        pw = os.environ.get("APP_DB_PASSWORD") or ""
        if role and pw:
            ensure_app_role(eng, role, pw)
        return 0
    finally:
        eng.dispose()


if __name__ == "__main__":
    sys.exit(main())

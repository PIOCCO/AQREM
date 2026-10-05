"""Idempotent DDL for databases created before newer model fields (no Alembic in MVP)."""

from sqlalchemy import Connection, text

# Columns added after initial deployments — safe to run on every startup.
_ANSWER_PATCHES = (
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS potentially_stale BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_detected_at TIMESTAMPTZ",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_reason TEXT",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS regeneration_backup JSONB",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS generation_source VARCHAR(32)",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS library_entry_id UUID",
)


def apply_schema_patches(conn: Connection) -> None:
    for stmt in _ANSWER_PATCHES:
        conn.execute(text(stmt))

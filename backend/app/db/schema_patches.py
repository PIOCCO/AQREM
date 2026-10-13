"""Idempotent DDL for databases created before newer model fields (no Alembic in MVP)."""

from sqlalchemy import Connection, text

# Columns added after initial deployments — safe to run on every startup.
_ORG_PATCHES = (
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS license_limit INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS license_status VARCHAR(32) NOT NULL DEFAULT 'active'",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_platform_admin BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_role VARCHAR(32)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_auth_version INTEGER NOT NULL DEFAULT 1",
    "UPDATE users SET platform_role = 'SUPER_ADMIN' WHERE is_platform_admin = true AND platform_role IS NULL",
    "ALTER TABLE audit_events ALTER COLUMN organization_id DROP NOT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true",
    "ALTER TABLE organization_memberships ADD COLUMN IF NOT EXISTS auth_version INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS owner_display_name VARCHAR(255)",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS chat_shares_enabled BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS chat_share_ttl_days INTEGER NOT NULL DEFAULT 7",
    "ALTER TABLE chat_conversation_shares ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
    "ALTER TABLE user_invitations ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ",
    """
    UPDATE organizations o SET license_limit = GREATEST(
        1,
        COALESCE((SELECT COUNT(*) FROM organization_memberships m WHERE m.organization_id = o.id), 0)
    )
    WHERE o.license_limit = 0 AND o.license_status = 'active'
    """,
)

_ANSWER_PATCHES = (
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS potentially_stale BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_detected_at TIMESTAMPTZ",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS stale_reason TEXT",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS regeneration_backup JSONB",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS generation_source VARCHAR(32)",
    "ALTER TABLE answers ADD COLUMN IF NOT EXISTS library_entry_id UUID",
)


def apply_schema_patches(conn: Connection) -> None:
    for stmt in _ORG_PATCHES:
        conn.execute(text(stmt))
    for stmt in _ANSWER_PATCHES:
        conn.execute(text(stmt))

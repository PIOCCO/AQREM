"""PostgreSQL row-level security (RLS) for shared-mode tenant isolation.

Mechanism (see docs/security-overview.md and docs/migrations.md, migration 3):

* Every table holding client data has RLS ENABLED and FORCED. The default policy (TO PUBLIC)
  is ``organization_id = current_setting('app.current_org', true)::uuid``. If the setting is
  unset or empty the comparison is NULL -> no rows visible, and INSERT/UPDATE fail WITH CHECK
  (fail closed).
* The app sets ``app.current_org`` transaction-locally (``set_config(..., true)`` == SET LOCAL)
  at the start of every transaction of a session that was scoped with
  :func:`scope_session_to_org`. ``open_tenant_session`` (API requests via get_tenant_db and every
  Celery task) always scopes, so workers/beat cannot touch tenant data without an org.
* Two NOLOGIN group roles carry the only exceptions (no role uses the BYPASSRLS attribute):
    - ``aqrem_rls_control``: control-plane membership. Policies on *control-plane* tables
      (users, organizations, memberships, invitations, join links, password resets, ...) allow
      this group all rows, because login-by-email, invitations, org creation and the super-admin
      console are legitimately cross-org. It gets NOTHING extra on tenant data tables
      (documents, chunks, sources, answers, audit, ...), except platform audit rows whose
      organization_id IS NULL.
    - ``aqrem_rls_bypass``: migration role and the named support role (``aqrem_support``) only.
* A separate data-plane role (TENANT_DATABASE_URL, e.g. ``aqrem_tenant``) that is NOT a member of
  ``aqrem_rls_control`` sees only the current org's rows even on control-plane tables.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

ORG_SETTING = "app.current_org"
CONTROL_GROUP = "aqrem_rls_control"
BYPASS_GROUP = "aqrem_rls_bypass"
SUPPORT_ROLE = "aqrem_support"
_INFO_KEY = "aqrem_current_org"

CURRENT_ORG_SQL = f"NULLIF(current_setting('{ORG_SETTING}', true), '')::uuid"

# Tenant data plane: strictly org-scoped for everyone except the bypass group.
TENANT_ORG_TABLES: tuple[str, ...] = (
    "access_group_memberships",
    "access_groups",
    "answer_library_entries",
    "answer_staleness_events",
    "answers",
    "audit_events",  # + control-plane group may see/insert rows with organization_id IS NULL
    "chat_conversation_shares",
    "client_documents",
    "evidence_item_versions",
    "evidence_items",
    "github_connections",
    "github_repo_configs",
    "ingestion_ignore_rules",
    "projects",
    "questionnaires",
    "questions",
    "source_sync_jobs",
    "sources",
)
# Link tables without organization_id: visible iff the parent row is visible (parent is RLS'd).
TENANT_CHILD_TABLES: dict[str, str] = {
    "answer_evidence_links": "EXISTS (SELECT 1 FROM answers p WHERE p.id = answer_id)",
    "answer_library_evidence_links": (
        "EXISTS (SELECT 1 FROM answer_library_entries p WHERE p.id = library_entry_id)"
    ),
}
# Control plane: current org only for ordinary roles; all rows for aqrem_rls_control.
CONTROL_ORG_TABLES: tuple[str, ...] = (
    "client_credential_metadata",
    "client_environments",
    "control_plane_events",
    "email_delivery_logs",
    "employee_join_links",
    "employee_join_pending",
    "organization_join_blocklist",
    "organization_memberships",
    "provisioning_jobs",
    "public_chat_share_index",
    "tenant_data_store_configs",
    "user_invitations",
)
CONTROL_SPECIAL_TABLES: dict[str, str] = {
    "organizations": f"id = {CURRENT_ORG_SQL}",
    # A user is visible to the data plane only if they belong to the current org.
    "users": (
        "EXISTS (SELECT 1 FROM organization_memberships m WHERE m.user_id = users.id "
        f"AND m.organization_id = {CURRENT_ORG_SQL})"
    ),
    # Token tables have no org; only the control plane may read them.
    "password_reset_tokens": "false",
    "employee_join_verifications": "false",
}
# Deliberately excluded (no client data): aqrem_schema_versions, schema_migrations.

ALL_RLS_TABLES: tuple[str, ...] = (
    TENANT_ORG_TABLES + tuple(TENANT_CHILD_TABLES) + CONTROL_ORG_TABLES + tuple(CONTROL_SPECIAL_TABLES)
)


def _ensure_group(conn: Connection, name: str) -> None:
    conn.execute(text(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{name}') THEN "
        f"CREATE ROLE {name} NOLOGIN NOINHERIT; END IF; END $$"
    ))


def _is_direct_member(conn: Connection, member: str, group: str) -> bool:
    return bool(conn.execute(text(
        "SELECT 1 FROM pg_auth_members m JOIN pg_roles g ON g.oid = m.roleid JOIN pg_roles u ON u.oid = m.member "
        "WHERE g.rolname = :g AND u.rolname = :u"), {"g": group, "u": member}).scalar())


def _policy(conn: Connection, table: str, name: str, role: str, using: str, check: str | None = None) -> None:
    exists = conn.execute(
        text("SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = :t AND policyname = :p"),
        {"t": table, "p": name},
    ).scalar()
    if exists:
        conn.execute(text(f"DROP POLICY {name} ON {table}"))  # policy-only replace; no data touched
    conn.execute(text(
        f"CREATE POLICY {name} ON {table} AS PERMISSIVE FOR ALL TO {role} "
        f"USING ({using}) WITH CHECK ({check or using})"
    ))


def apply_rls(conn: Connection) -> None:
    """Idempotently create group roles, policies, and ENABLE + FORCE RLS. Non-destructive."""
    for g in (CONTROL_GROUP, BYPASS_GROUP):
        _ensure_group(conn, g)
    # The migration role owns the tables; FORCE RLS applies to owners, so it must bypass.
    me = conn.execute(text("SELECT current_user")).scalar()
    is_super = conn.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar()
    _ensure_group(conn, SUPPORT_ROLE)
    for member in ([] if is_super else [me]) + [SUPPORT_ROLE]:
        if not _is_direct_member(conn, member, BYPASS_GROUP):
            try:
                with conn.begin_nested():
                    conn.execute(text(f'GRANT {BYPASS_GROUP} TO "{member}"'))
            except Exception as exc:
                raise RuntimeError(
                    f"RLS migration: cannot grant {BYPASS_GROUP} to {member}. As the server admin run: "
                    f"GRANT {BYPASS_GROUP}, {CONTROL_GROUP} TO {me} WITH ADMIN OPTION; then rerun migrations."
                ) from exc

    existing = {r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))}
    org = f"organization_id = {CURRENT_ORG_SQL}"
    for t in TENANT_ORG_TABLES:
        if t in existing:
            _policy(conn, t, "aqrem_org_isolation", "PUBLIC", org)
    for t, expr in TENANT_CHILD_TABLES.items():
        if t in existing:
            _policy(conn, t, "aqrem_org_isolation", "PUBLIC", expr)
    for t in CONTROL_ORG_TABLES:
        if t in existing:
            _policy(conn, t, "aqrem_org_isolation", "PUBLIC", org)
            _policy(conn, t, "aqrem_control_plane", CONTROL_GROUP, "true")
    for t, expr in CONTROL_SPECIAL_TABLES.items():
        if t in existing:
            _policy(conn, t, "aqrem_org_isolation", "PUBLIC", expr)
            _policy(conn, t, "aqrem_control_plane", CONTROL_GROUP, "true")
    if "audit_events" in existing:
        _policy(conn, "audit_events", "aqrem_platform_audit", CONTROL_GROUP, "organization_id IS NULL")
    for t in ALL_RLS_TABLES:
        if t in existing:
            _policy(conn, t, "aqrem_bypass", BYPASS_GROUP, "true")
            conn.execute(text(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY"))


def scope_session_to_org(session: Session, organization_id: UUID | str | None) -> None:
    """Bind ``session`` to one organization for RLS (SET LOCAL app.current_org).

    Applied now (if a transaction is open) and re-applied at the start of every later transaction
    of the session. Passing None clears it (fail closed: no tenant rows).
    """
    value = str(organization_id) if organization_id else ""
    if session.info.get(_INFO_KEY, "") == value and session.in_transaction():
        return
    session.info[_INFO_KEY] = value
    if session.in_transaction():
        session.execute(text("SELECT set_config(:k, :v, true)"), {"k": ORG_SETTING, "v": value})


def ensure_org_scope(session: Session, organization_id: UUID | str | None) -> None:
    """Scope an *unscoped* session (control-plane writes such as audit rows). A session already
    bound to an org is left alone, so a mismatched write is rejected by the WITH CHECK policy."""
    if organization_id and not session.info.get(_INFO_KEY):
        scope_session_to_org(session, organization_id)


def current_session_org(session: Session) -> str:
    return session.info.get(_INFO_KEY, "")


@event.listens_for(Session, "after_begin")
def _apply_org_on_begin(session: Session, transaction, connection: Connection) -> None:
    value = session.info.get(_INFO_KEY)
    if value is None or connection.dialect.name != "postgresql":
        return
    connection.execute(text("SELECT set_config(:k, :v, true)"), {"k": ORG_SETTING, "v": value})

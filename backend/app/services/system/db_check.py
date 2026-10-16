"""'Test database' check for shared, dedicated and bring-your-own PostgreSQL.

Each check returns ok / warn / fail with a message an operator can act on.
Never includes the password or full connection string in output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

MIN_SERVER_VERSION = 140000  # PostgreSQL 14
MAX_TESTED_MAJOR = 17
REQUIRED_TABLE_PRIVS = ("SELECT", "INSERT", "UPDATE", "DELETE")
CORE_TABLES = ("organizations", "users", "evidence_items", "client_documents", "audit_events")


@dataclass
class Check:
    name: str
    status: str  # ok | warn | fail | skipped
    message: str


@dataclass
class DatabaseReport:
    target: str
    role: str  # app | migration
    ok: bool
    checks: list[Check] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"target": self.target, "role": self.role, "ok": self.ok, "checks": [asdict(c) for c in self.checks]}


def safe_target(url: str) -> str:
    try:
        u = make_url(url)
        return f"{u.host or 'localhost'}:{u.port or 5432}/{u.database or ''} as {u.username or '?'}"
    except Exception:
        return "<unparseable DATABASE_URL>"


def explain_connect_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "password authentication failed" in msg:
        return "Login rejected: wrong user name or password for this database role."
    if "could not translate host name" in msg or "name or service not known" in msg or "nodename nor servname" in msg:
        return "Host name does not resolve. For private endpoints check the private DNS zone link to the VNet."
    if "timeout" in msg or "timed out" in msg:
        return "Connection timed out. Check firewall rules / NSG / private endpoint and that the server is running."
    if "connection refused" in msg:
        return "Connection refused: nothing is listening on that host/port."
    if "does not exist" in msg and "database" in msg:
        return "The database name does not exist on the server; create it first."
    if "no pg_hba.conf entry" in msg or "ssl" in msg and "required" in msg:
        return "Server requires TLS: add sslmode=require (or verify-full) to the connection URL."
    if "certificate" in msg:
        return "TLS certificate verification failed; check sslrootcert / sslmode=verify-full settings."
    return f"Could not connect ({type(exc).__name__})."


def run_database_checks(
    url: str,
    *,
    role: str = "app",
    require_tls: bool = False,
    engine: Engine | None = None,
) -> DatabaseReport:
    report = DatabaseReport(target=safe_target(url), role=role, ok=False)
    checks = report.checks
    own_engine = engine is None
    try:
        eng = engine or create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    except Exception as exc:
        checks.append(Check("connection", "fail", f"Invalid connection URL ({type(exc).__name__})."))
        return report
    try:
        with eng.connect() as conn:
            checks.append(Check("connection", "ok", "Connected."))
            ver = int(conn.execute(text("SHOW server_version_num")).scalar() or 0)
            major = ver // 10000
            if ver < MIN_SERVER_VERSION:
                checks.append(Check("version", "fail", f"PostgreSQL {major} is not supported; use 14 or newer (16 recommended)."))
            elif major > MAX_TESTED_MAJOR:
                checks.append(Check("version", "warn", f"PostgreSQL {major} has not been tested; 14–{MAX_TESTED_MAJOR} are supported."))
            else:
                checks.append(Check("version", "ok", f"PostgreSQL {major}."))

            ssl = conn.execute(text("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")).scalar()
            if ssl:
                checks.append(Check("tls", "ok", "Connection is encrypted (TLS)."))
            elif require_tls:
                checks.append(Check("tls", "fail", "Connection is NOT encrypted. Add sslmode=require (or verify-full) to the URL."))
            else:
                checks.append(Check("tls", "warn", "Connection is not encrypted (acceptable only on a local/lab network)."))

            installed = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).scalar()
            available = conn.execute(
                text("SELECT default_version FROM pg_available_extensions WHERE name='vector'")
            ).scalar()
            if installed:
                checks.append(Check("vector_extension", "ok", f"pgvector {installed} installed."))
            elif available:
                level = "warn" if role == "app" else "ok"
                checks.append(Check(
                    "vector_extension", level,
                    f"pgvector {available} is available but not installed; the migration job runs CREATE EXTENSION vector.",
                ))
            else:
                checks.append(Check(
                    "vector_extension", "fail",
                    "pgvector is not available on this server. On Azure Flexible Server add VECTOR to the "
                    "azure.extensions server parameter; elsewhere install the pgvector package.",
                ))

            info = conn.execute(text(
                "SELECT current_user, rolsuper, has_schema_privilege(current_user, current_schema(), 'USAGE'), "
                "has_schema_privilege(current_user, current_schema(), 'CREATE'), current_schema() "
                "FROM pg_roles WHERE rolname = current_user"
            )).first()
            user, is_super, usage, create, schema = info if info else ("?", False, False, False, "public")
            if not usage:
                checks.append(Check("permissions", "fail", f"Role {user} has no USAGE on schema {schema}."))
            elif role == "migration":
                if create:
                    checks.append(Check("permissions", "ok", f"Role {user} can create objects in schema {schema}."))
                else:
                    checks.append(Check("permissions", "fail", f"Migration role {user} lacks CREATE on schema {schema}."))
            else:
                existing = [
                    t for t in CORE_TABLES
                    if conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{schema}.{t}"}).scalar()
                ]
                missing = []
                for t in existing:
                    for priv in REQUIRED_TABLE_PRIVS:
                        if not conn.execute(
                            text("SELECT has_table_privilege(current_user, :t, :p)"), {"t": f"{schema}.{t}", "p": priv}
                        ).scalar():
                            missing.append(f"{priv} on {t}")
                if not existing:
                    checks.append(Check("permissions", "warn", "Schema not migrated yet; run the migration job first."))
                elif missing:
                    checks.append(Check("permissions", "fail", f"Role {user} is missing: {', '.join(missing[:6])}. "
                                        "Run docs/sql/app_role.sql as the owner."))
                else:
                    checks.append(Check("permissions", "ok", f"Role {user} can read and write application tables."))
                if is_super or create:
                    checks.append(Check(
                        "least_privilege", "warn",
                        f"App role {user} is {'a superuser' if is_super else 'allowed to CREATE in the schema'}; "
                        "use a separate migration role (MIGRATION_DATABASE_URL) and a restricted app role.",
                    ))
                else:
                    checks.append(Check("least_privilege", "ok", "App role cannot run DDL."))
    except Exception as exc:
        if not checks:
            checks.append(Check("connection", "fail", explain_connect_error(exc)))
        else:
            checks.append(Check("query", "fail", f"Check aborted ({type(exc).__name__})."))
    finally:
        if own_engine:
            try:
                eng.dispose()
            except Exception:
                pass
    report.ok = all(c.status != "fail" for c in checks)
    return report

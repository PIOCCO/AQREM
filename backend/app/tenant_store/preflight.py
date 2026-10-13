"""Preflight checks for customer PostgreSQL (no superuser required)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import create_engine, text

from app.tenant_store.exceptions import TenantHostRejected, TenantStoreUnavailable
from app.tenant_store.masking import mask_message
from app.tenant_store.migrations import migrate_tenant_engine
from app.tenant_store.ssrf import validate_host_port


@dataclass
class PreflightCheck:
    id: str
    title: str
    status: str  # pass | fail | warn
    detail: str


@dataclass
class PreflightReport:
    ok: bool
    checks: list[PreflightCheck] = field(default_factory=list)
    latency_ms: int | None = None


def run_preflight(
    *,
    host: str,
    port: int | None,
    database_name: str,
    username: str,
    password: str,
    ssl_mode: str = "verify-full",
    connection_method: str = "public_tls",
    schema_name: str = "public",
) -> PreflightReport:
    checks: list[PreflightCheck] = []
    if ssl_mode in {"disable", "allow", "prefer"}:
        return PreflightReport(
            ok=False,
            checks=[
                PreflightCheck(
                    "tls",
                    "Encrypted connection",
                    "fail",
                    "Unencrypted connections are not allowed. Set SSL mode to verify-full.",
                )
            ],
        )

    allow_private = connection_method in {"private_link", "vpn", "secure_connector", "customer_deployed"}
    try:
        resolved = validate_host_port(host, port, allow_private=allow_private)
        checks.append(
            PreflightCheck(
                "dns",
                "Host resolution",
                "pass",
                f"Resolved {resolved.hostname} to {len(resolved.addresses)} address(es).",
            )
        )
    except TenantHostRejected as exc:
        checks.append(PreflightCheck("dns", "Host resolution", "fail", str(exc)))
        return PreflightReport(ok=False, checks=checks)

    from urllib.parse import quote_plus

    url = (
        f"postgresql+psycopg://{quote_plus(username)}:{quote_plus(password)}"
        f"@{host}:{port or 5432}/{quote_plus(database_name)}?sslmode={quote_plus(ssl_mode)}"
    )

    started = time.perf_counter()
    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            latency_ms = int((time.perf_counter() - started) * 1000)
            ver = conn.execute(text("SHOW server_version_num")).scalar()
            ver_int = int(ver)
            if ver_int < 140000 or ver_int >= 180000:
                checks.append(
                    PreflightCheck(
                        "version",
                        "PostgreSQL version",
                        "fail",
                        "Supported versions are PostgreSQL 14, 15, 16, and 17.",
                    )
                )
            else:
                checks.append(
                    PreflightCheck(
                        "version",
                        "PostgreSQL version",
                        "pass",
                        f"Server reports version num {ver}.",
                    )
                )

            ext = conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar()
            if ext:
                checks.append(PreflightCheck("vector", "pgvector extension", "pass", "vector is installed."))
            else:
                checks.append(
                    PreflightCheck(
                        "vector",
                        "pgvector extension",
                        "warn",
                        "pgvector is missing. Semantic search will be limited until your DBA installs it.",
                    )
                )

            conn.execute(text(f'SET search_path TO "{schema_name.replace(chr(34), "")}"'))
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS __aqrem_preflight_probe (
                        id SERIAL PRIMARY KEY,
                        probe_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
            )
            conn.execute(text("INSERT INTO __aqrem_preflight_probe DEFAULT VALUES"))
            conn.execute(text("DELETE FROM __aqrem_preflight_probe"))
            conn.commit()
            checks.append(PreflightCheck("write", "Write and read", "pass", "Test row written and removed."))

        mig = migrate_tenant_engine(engine, dry_run=True)
        checks.append(
            PreflightCheck(
                "migrations",
                "Schema migrations",
                "pass" if mig.status != "failed" else "fail",
                mig.detail,
            )
        )
        ok = all(c.status != "fail" for c in checks)
        return PreflightReport(ok=ok, checks=checks, latency_ms=latency_ms)
    except Exception as exc:
        safe = mask_message(str(exc))
        checks.append(
            PreflightCheck(
                "connect",
                "Database connection",
                "fail",
                f"Could not connect: {safe}",
            )
        )
        return PreflightReport(ok=False, checks=checks)

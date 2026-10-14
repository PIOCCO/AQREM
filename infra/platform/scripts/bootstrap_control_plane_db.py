#!/usr/bin/env python3
"""Idempotent control-plane PostgreSQL bootstrap: migrations + gateway role grant + verification."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg

MIGRATIONS = [
    "001_platform_schema.sql",
    "002_gateway_schema.sql",
    "003_gateway_least_privilege_role.sql",
    "004_tenant_embedding_metadata.sql",
    "005_platform_component_roles.sql",
]


def _token() -> str:
    return subprocess.check_output(
        ["az", "account", "get-access-token", "--resource-type", "oss-rdbms", "-o", "tsv"],
        text=True,
    ).strip()


def _connect(host: str, db: str, user: str) -> psycopg.Connection:
    return psycopg.connect(
        host=host,
        dbname=db,
        user=user,
        password=_token(),
        sslmode="require",
    )


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> None:
    for name in MIGRATIONS:
        path = migrations_dir / name
        sql = path.read_text(encoding="utf-8")
        conn.execute(sql)
        conn.commit()
        print(f"applied {name}")


def ensure_gateway_principal(conn: psycopg.Connection, gateway_mi_name: str) -> None:
    conn.execute("SELECT * FROM pgaadauth_create_principal(%s, false, false)", (gateway_mi_name,))
    conn.execute(f'GRANT aqrem_gateway_app TO "{gateway_mi_name}"')
    conn.commit()


def verify_gateway_grant(conn: psycopg.Connection, gateway_mi_name: str) -> None:
    row = conn.execute(
        """
        SELECT pg_has_role(%s::name, 'aqrem_gateway_app'::name, 'member') AS ok
        """,
        (gateway_mi_name,),
    ).fetchone()
    if not row or not row[0]:
        raise SystemExit(f"VERIFY FAILED: {gateway_mi_name} is not a member of aqrem_gateway_app")
    denied = conn.execute(
        """
        SELECT has_schema_privilege(%s, 'platform', 'USAGE') AS platform_usage
        """,
        (gateway_mi_name,),
    ).fetchone()
    if denied and denied[0]:
        raise SystemExit(f"VERIFY FAILED: {gateway_mi_name} has USAGE on platform schema")
    print(f"VERIFY OK: gateway MI {gateway_mi_name} has aqrem_gateway_app and no platform schema usage")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("CP_PG_HOST"))
    parser.add_argument("--database", default=os.environ.get("CP_PG_DATABASE", "aqrem_control"))
    parser.add_argument("--admin-user", default=os.environ.get("CP_PG_ADMIN_USER"))
    parser.add_argument("--gateway-mi-name", required=True)
    args = parser.parse_args()
    if not args.host or not args.admin_user:
        raise SystemExit("CP_PG_HOST and CP_PG_ADMIN_USER required")

    migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
    with _connect(args.host, args.database, args.admin_user) as conn:
        apply_migrations(conn, migrations_dir)
        ensure_gateway_principal(conn, args.gateway_mi_name)
        verify_gateway_grant(conn, args.gateway_mi_name)


if __name__ == "__main__":
    main()

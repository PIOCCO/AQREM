#!/usr/bin/env python3
"""Seed gateway.client + api_key for local prod stack (run once against postgres)."""

from __future__ import annotations

import os
import sys
import uuid

import bcrypt
import psycopg

DEFAULT_KEY = os.environ.get("GATEWAY_API_KEY", "local_dev_gateway_key_00000001")
CLIENT_ID = os.environ.get("GATEWAY_CLIENT_ID", "local-client")
ORG_ID = os.environ.get("SEED_ORG_ID", "00000000-0000-4000-8000-000000000001")


def main() -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL required", file=sys.stderr)
        return 1
    key_hash = bcrypt.hashpw(DEFAULT_KEY.encode("utf-8"), bcrypt.gensalt(rounds=10))
    prefix = DEFAULT_KEY[:8]
    with psycopg.connect(db_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute("CREATE SCHEMA IF NOT EXISTS gateway")
        conn.execute(
            """
            INSERT INTO gateway.client (client_id, organization_id, rpm_limit, tpm_limit, monthly_token_budget, active)
            VALUES (%s, %s, 120, 120000, 5000000, true)
            ON CONFLICT (client_id) DO UPDATE SET active = true
            """,
            (CLIENT_ID, uuid.UUID(ORG_ID)),
        )
        conn.execute(
            """
            INSERT INTO gateway.api_key (client_id, key_prefix, key_hash, label, active)
            VALUES (%s, %s, %s, 'primary', true)
            ON CONFLICT (client_id, label) DO UPDATE SET key_hash = EXCLUDED.key_hash, active = true
            """,
            (CLIENT_ID, prefix, key_hash),
        )
        conn.commit()
    print(f"Seeded gateway client={CLIENT_ID} org={ORG_ID} key_prefix={prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

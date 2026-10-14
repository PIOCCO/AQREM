from __future__ import annotations

import bcrypt

from app.config import Settings
from app.db import connection


def verify_api_key(settings: Settings, raw_key: str) -> dict | None:
    if not raw_key or len(raw_key) < 16:
        return None
    prefix = raw_key[:8]
    with connection(settings) as conn:
        rows = conn.execute(
            """
            SELECT c.client_id, c.organization_id, c.rpm_limit, c.tpm_limit, c.monthly_token_budget,
                   k.key_hash
            FROM gateway.api_key k
            JOIN gateway.client c ON c.client_id = k.client_id
            WHERE k.active AND c.active AND k.key_prefix = %s
            """,
            (prefix,),
        ).fetchall()
    for row in rows:
        if bcrypt.checkpw(raw_key.encode("utf-8"), bytes(row["key_hash"])):
            return {
                "client_id": row["client_id"],
                "organization_id": str(row["organization_id"]),
                "rpm_limit": row["rpm_limit"],
                "tpm_limit": row["tpm_limit"],
                "monthly_token_budget": row["monthly_token_budget"],
            }
    return None

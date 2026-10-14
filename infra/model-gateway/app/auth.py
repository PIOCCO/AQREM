from __future__ import annotations

import bcrypt

from app.config import Settings
from app.db import connection
from app.db_health import db_is_up, mark_db_down, mark_db_up
from app.key_cache import KeyValidationCache

_cache = KeyValidationCache(validation_ttl_seconds=60.0, revoke_propagation_seconds=60.0)


def configure_auth_cache(settings: Settings) -> None:
    global _cache
    _cache = KeyValidationCache(
        validation_ttl_seconds=settings.key_validation_cache_seconds,
        revoke_propagation_seconds=settings.key_revoke_max_seconds,
    )


def cache() -> KeyValidationCache:
    return _cache


def verify_api_key(settings: Settings, raw_key: str) -> dict | None:
    if not raw_key or len(raw_key) < 16:
        return None

    cached = _cache.get_if_valid(raw_key)
    if cached:
        return cached

    if not db_is_up():
        return None

    prefix = raw_key[:8]
    try:
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
        mark_db_up()
    except Exception:
        mark_db_down()
        return None

    for row in rows:
        if bcrypt.checkpw(raw_key.encode("utf-8"), bytes(row["key_hash"])):
            client = {
                "client_id": row["client_id"],
                "organization_id": str(row["organization_id"]),
                "rpm_limit": row["rpm_limit"],
                "tpm_limit": row["tpm_limit"],
                "monthly_token_budget": row["monthly_token_budget"],
            }
            _cache.remember_valid(raw_key, client)
            return client
    return None

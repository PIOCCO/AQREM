"""Redis / Celery broker reachability (no secrets in errors)."""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def assert_broker_available() -> None:
    settings = get_settings()
    url = (settings.redis_url or "").strip()
    if not url:
        raise RuntimeError("REDIS_URL is not configured.")
    try:
        import redis

        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
    except Exception as exc:
        raise RuntimeError(
            "Task queue broker is unavailable. Start Redis before uploading or indexing."
        ) from exc


def broker_is_available() -> bool:
    try:
        assert_broker_available()
        return True
    except RuntimeError:
        return False

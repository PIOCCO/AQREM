"""Optional RAG debug logging (enable with DEBUG_RAG=1)."""

from __future__ import annotations

import json
import logging
from uuid import UUID

from app.core.config import get_settings

logger = logging.getLogger("aqrem.rag")


def debug_rag_enabled() -> bool:
    return bool(get_settings().debug_rag)


def log_rag_event(event: str, **fields: object) -> None:
    if not debug_rag_enabled():
        return
    safe = {k: (str(v) if isinstance(v, UUID) else v) for k, v in fields.items()}
    logger.info("RAG %s %s", event, json.dumps(safe, default=str))

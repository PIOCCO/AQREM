"""Model gateway configuration validation (no secrets in messages)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import Settings


@dataclass(frozen=True)
class GatewayConfigStatus:
    configured: bool
    missing: tuple[str, ...]
    gateway_host: str | None


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url.strip()).netloc or None
    except Exception:
        return None


def inspect_gateway(settings: Settings) -> GatewayConfigStatus:
    missing: list[str] = []
    if not (settings.gateway_url or "").strip():
        missing.append("GATEWAY_URL")
    # Per-organization model tokens may supply keys at request time; platform key is optional in lab.
    if not (settings.gateway_chat_alias or "").strip():
        missing.append("GATEWAY_CHAT_ALIAS")
    if not (settings.gateway_embeddings_alias or "").strip():
        missing.append("GATEWAY_EMBEDDINGS_ALIAS")
    return GatewayConfigStatus(
        configured=len(missing) == 0,
        missing=tuple(missing),
        gateway_host=_host(settings.gateway_url),
    )


def require_gateway(settings: Settings) -> None:
    if settings.llm_provider.lower().strip() != "gateway":
        return
    status = inspect_gateway(settings)
    if not status.configured:
        raise RuntimeError(
            "LLM_PROVIDER=gateway but gateway is not fully configured. Missing: "
            + ", ".join(status.missing)
        )

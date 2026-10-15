"""Resolve per-organization gateway API keys (never log values)."""

from __future__ import annotations

from uuid import UUID

from app.core.config import Settings, get_settings
from app.services.client_secrets.vault_store import get_client_secret_store


def resolve_gateway_api_key(organization_id: UUID | None, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if organization_id is not None:
        token = get_client_secret_store().read_model_token(organization_id)
        if token and token.strip():
            return token.strip()
    key = (settings.gateway_api_key or "").strip()
    if not key:
        raise RuntimeError("No gateway API key configured for this organization.")
    return key

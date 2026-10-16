"""Model provider configuration validation (no secrets in error messages)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings

logger = logging.getLogger("aqrem.providers")

_FAKE_GATEWAY_MARKERS = (
    "fake-azure-openai",
    "fake.invalid",
    "fake-azure",
)


@dataclass(frozen=True)
class AzureOpenAIConfigStatus:
    configured: bool
    auth_mode: str  # api_key | managed_identity | none
    missing: tuple[str, ...]
    endpoint_host: str | None


def _endpoint_host(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(endpoint.strip())
        return parsed.netloc or None
    except Exception:
        return None


def inspect_azure_openai(settings: Settings) -> AzureOpenAIConfigStatus:
    missing: list[str] = []
    if not (settings.azure_openai_endpoint or "").strip():
        missing.append("AZURE_OPENAI_ENDPOINT")
    if settings.azure_openai_use_managed_identity:
        auth_mode = "managed_identity"
    elif (settings.azure_openai_api_key or "").strip():
        auth_mode = "api_key"
    else:
        auth_mode = "none"
        missing.append("AZURE_OPENAI_API_KEY or AZURE_OPENAI_USE_MANAGED_IDENTITY=true")
    if not (settings.azure_openai_chat_deployment or "").strip():
        missing.append("AZURE_OPENAI_CHAT_DEPLOYMENT (or AZURE_OPENAI_DEPLOYMENT)")
    if not (settings.azure_openai_embedding_deployment or "").strip():
        missing.append("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    if not (settings.azure_openai_api_version or "").strip():
        missing.append("AZURE_OPENAI_API_VERSION")
    if "embedding_dimensions" not in settings.model_fields_set or settings.embedding_dimensions <= 0:
        missing.append("EMBEDDING_DIMENSIONS")
    configured = len(missing) == 0
    return AzureOpenAIConfigStatus(
        configured=configured,
        auth_mode=auth_mode,
        missing=tuple(missing),
        endpoint_host=_endpoint_host(settings.azure_openai_endpoint),
    )


def azure_missing_message(missing: tuple[str, ...] | list[str]) -> str:
    """Fail-fast text naming the missing variables (never their values)."""
    return (
        "LLM_PROVIDER=azure but Azure OpenAI is not fully configured. Missing: "
        + ", ".join(missing)
        + ". Set these in your .env file (see .env.example and docs/azure-openai-setup.md), "
        "then rebuild/restart the api and worker containers."
    )


def require_azure_openai(settings: Settings) -> None:
    """Raise when Azure provider is selected but configuration is incomplete."""
    if settings.llm_provider.lower() != "azure":
        return
    status = inspect_azure_openai(settings)
    if not status.configured:
        raise RuntimeError(azure_missing_message(status.missing))


def validate_llm_startup(settings: Settings) -> None:
    """Fail fast at api/worker startup when the selected provider cannot work.

    Messages name variables only, never secret values.
    """
    provider = settings.llm_provider.lower().strip()
    if provider in {"mock", "local", "fake", "test", ""} and settings.app_env == "production":
        raise RuntimeError(
            "Production refuses to start with a mock or fake LLM provider "
            f"(LLM_PROVIDER={provider or 'unset'}). Set LLM_PROVIDER=azure."
        )
    if provider == "azure":
        require_azure_openai(settings)
    elif provider == "openai" and not (settings.openai_api_key or "").strip():
        raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")


def gateway_points_at_fake(settings: Settings) -> bool:
    """True when the configured gateway URL is a known local fake/test upstream."""
    blob = (settings.gateway_url or "").lower()
    return any(marker in blob for marker in _FAKE_GATEWAY_MARKERS)


def llm_provider_summary(settings: Settings) -> dict[str, str | bool | int]:
    provider = settings.llm_provider.lower().strip()
    dim = settings.embedding_dimensions
    if provider == "azure":
        status = inspect_azure_openai(settings)
        return {
            "provider": "azure",
            "llm_provider": "azure",
            "embedding_provider": "azure",
            "configured": status.configured,
            "auth_mode": status.auth_mode,
            "endpoint": status.endpoint_host or "",
            "chat_deployment": settings.azure_openai_chat_deployment,
            "embedding_deployment": settings.azure_openai_embedding_deployment,
            "chat_model": f"azure:{settings.azure_openai_chat_deployment}",
            "embedding_model": f"azure:{settings.azure_openai_embedding_deployment}:{dim}",
            "dimensions": dim,
        }
    if provider == "gateway":
        from app.core.gateway_config import inspect_gateway

        status = inspect_gateway(settings)
        return {
            "provider": "gateway",
            "llm_provider": "gateway",
            "embedding_provider": "gateway",
            "configured": status.configured and not gateway_points_at_fake(settings),
            "auth_mode": "api_key",
            "endpoint": status.gateway_host or "",
            "chat_alias": settings.gateway_chat_alias,
            "embedding_alias": settings.gateway_embeddings_alias,
            "chat_model": f"gateway:{settings.gateway_chat_alias}",
            "embedding_model": f"gateway:{settings.gateway_embeddings_alias}:{dim}",
            "dimensions": dim,
            "fake_upstream": gateway_points_at_fake(settings),
        }
    if provider == "openai":
        return {
            "provider": "openai",
            "llm_provider": "openai",
            "embedding_provider": "openai",
            "configured": bool((settings.openai_api_key or "").strip()),
            "auth_mode": "api_key",
            "chat_model": f"openai:{settings.openai_chat_model}",
            "embedding_model": f"openai:{settings.openai_embedding_model}:{dim}",
            "dimensions": dim,
        }
    if provider in {"mock", "local"}:
        return {
            "provider": provider,
            "llm_provider": provider,
            "embedding_provider": provider,
            "configured": settings.app_env != "production",
            "auth_mode": "n/a",
            "chat_model": "local-extractive",
            "embedding_model": f"local-deterministic-hash-{dim}",
            "dimensions": dim,
        }
    return {
        "provider": provider,
        "llm_provider": provider,
        "embedding_provider": provider,
        "configured": False,
        "auth_mode": "n/a",
        "chat_model": provider or "unset",
        "embedding_model": provider or "unset",
        "dimensions": dim,
    }


def log_active_providers(role: str) -> None:
    """Startup line naming the LLM and embedding providers actually in use."""
    from app.core.config import get_settings

    settings = get_settings()
    summary = llm_provider_summary(settings)
    logger.info(
        "Active providers: role=%s llm=%s chat_model=%s embeddings=%s embedding_model=%s dimensions=%s"
        " endpoint_host=%s auth=%s",
        role,
        summary.get("llm_provider"),
        summary.get("chat_model"),
        summary.get("embedding_provider"),
        summary.get("embedding_model"),
        summary.get("dimensions"),
        summary.get("endpoint") or "-",
        summary.get("auth_mode"),
    )

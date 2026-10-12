"""Azure OpenAI configuration validation (no secrets in error messages)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


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
    configured = len(missing) == 0
    return AzureOpenAIConfigStatus(
        configured=configured,
        auth_mode=auth_mode,
        missing=tuple(missing),
        endpoint_host=_endpoint_host(settings.azure_openai_endpoint),
    )


def require_azure_openai(settings: Settings) -> None:
    """Raise when Azure provider is selected but configuration is incomplete."""
    if settings.llm_provider.lower() != "azure":
        return
    status = inspect_azure_openai(settings)
    if not status.configured:
        raise RuntimeError(
            "LLM_PROVIDER=azure but Azure OpenAI is not fully configured. Missing: "
            + ", ".join(status.missing)
        )


def llm_provider_summary(settings: Settings) -> dict[str, str | bool]:
    provider = settings.llm_provider.lower()
    if provider == "azure":
        status = inspect_azure_openai(settings)
        return {
            "provider": "azure",
            "configured": status.configured,
            "auth_mode": status.auth_mode,
            "endpoint": status.endpoint_host or "",
            "chat_deployment": settings.azure_openai_chat_deployment,
            "embedding_deployment": settings.azure_openai_embedding_deployment,
        }
    return {"provider": provider, "configured": True, "auth_mode": "n/a"}

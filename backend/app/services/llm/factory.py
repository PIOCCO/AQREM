from functools import lru_cache
from uuid import UUID

from app.core.config import get_settings
from app.core.llm_config import require_azure_openai
from app.services.llm.base import LLMProvider
from app.services.llm.gateway_keys import resolve_gateway_api_key
from app.services.llm.mock import MockLLMProvider


@lru_cache
def _cached_mock(dimensions: int, provider_name: str) -> LLMProvider:
    return MockLLMProvider(dimensions=dimensions, provider_name=provider_name)


@lru_cache
def _cached_azure(settings_fingerprint: str) -> LLMProvider:
    settings = get_settings()
    require_azure_openai(settings)
    from app.services.llm.azure_openai import AzureOpenAIProvider

    return AzureOpenAIProvider(settings)


@lru_cache
def _cached_gateway(api_key_fingerprint: str) -> LLMProvider:
    settings = get_settings()
    from app.services.llm.gateway import GatewayLLMProvider

    api_key = resolve_gateway_api_key(None)
    return GatewayLLMProvider(settings, api_key=api_key)


@lru_cache
def _cached_openai(fingerprint: str) -> LLMProvider:
    settings = get_settings()
    from app.services.llm.openai_provider import OpenAIProvider

    return OpenAIProvider(settings)


def get_llm_provider(organization_id: UUID | None = None) -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider == "gateway":
        from app.core.gateway_config import require_gateway
        from app.core.llm_config import gateway_points_at_fake
        from app.services.llm.gateway import GatewayLLMProvider

        if settings.app_env == "production" and gateway_points_at_fake(settings):
            raise RuntimeError(
                "Production refuses to start with a mock or fake model provider. "
                "GATEWAY_URL points at a fake or test upstream."
            )
        require_gateway(settings)
        api_key = resolve_gateway_api_key(organization_id)
        fp = f"{api_key[:4]}:{api_key[-4:]}" if len(api_key) >= 8 else "short"
        if organization_id is None and fp:
            return _cached_gateway(fp)
        return GatewayLLMProvider(settings, api_key=api_key)
    if provider == "azure":
        fp = (
            f"{settings.azure_openai_endpoint}:{settings.azure_openai_chat_deployment}:"
            f"{settings.azure_openai_embedding_deployment}"
        )
        return _cached_azure(fp)
    if provider == "openai":
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
        fp = f"{key[:4]}:{key[-4:]}:{settings.openai_chat_model}:{settings.openai_embedding_model}:{settings.embedding_dimensions}"
        return _cached_openai(fp)
    if provider in {"mock", "local"}:
        if settings.app_env == "production":
            raise RuntimeError(
                "Production refuses to start with a mock or fake LLM provider "
                f"(LLM_PROVIDER={provider}). The deterministic local provider is "
                "allowed only when APP_ENV is not production."
            )
        return _cached_mock(settings.embedding_dimensions, provider)
    raise RuntimeError(
        f"Unknown LLM_PROVIDER={provider!r}. Expected openai, gateway, azure, "
        "or local/mock (non-production only)."
    )


def reset_llm_provider_cache() -> None:
    _cached_mock.cache_clear()
    _cached_azure.cache_clear()
    _cached_gateway.cache_clear()
    _cached_openai.cache_clear()

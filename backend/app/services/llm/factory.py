from functools import lru_cache
from uuid import UUID

from app.core.config import get_settings
from app.core.llm_config import require_azure_openai
from app.services.llm.base import LLMProvider
from app.services.llm.gateway_keys import resolve_gateway_api_key
from app.services.llm.mock import MockLLMProvider


@lru_cache
def _cached_mock(dimensions: int) -> LLMProvider:
    return MockLLMProvider(dimensions=dimensions)


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


def get_llm_provider(organization_id: UUID | None = None) -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider == "gateway":
        from app.core.gateway_config import require_gateway
        from app.services.llm.gateway import GatewayLLMProvider

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
    if provider == "mock":
        return _cached_mock(settings.embedding_dimensions)
    return _cached_mock(settings.embedding_dimensions)


def reset_llm_provider_cache() -> None:
    _cached_mock.cache_clear()
    _cached_azure.cache_clear()
    _cached_gateway.cache_clear()

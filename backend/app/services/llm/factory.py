from functools import lru_cache

from app.core.config import get_settings
from app.core.llm_config import require_azure_openai
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()
    if provider == "azure":
        require_azure_openai(settings)
        from app.services.llm.azure_openai import AzureOpenAIProvider

        return AzureOpenAIProvider(settings)
    if provider == "mock":
        return MockLLMProvider(dimensions=settings.embedding_dimensions)
    # Legacy default for local dev when LLM_PROVIDER unset or unknown
    return MockLLMProvider(dimensions=settings.embedding_dimensions)


def reset_llm_provider_cache() -> None:
    get_llm_provider.cache_clear()

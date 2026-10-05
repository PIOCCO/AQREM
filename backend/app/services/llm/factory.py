from functools import lru_cache

from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.mock import MockLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "azure" and settings.azure_openai_api_key:
        from app.services.llm.azure_openai import AzureOpenAIProvider

        return AzureOpenAIProvider(settings)
    return MockLLMProvider(dimensions=settings.embedding_dimensions)

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.llm.azure_openai import AzureOpenAIProvider
from app.services.llm.base import AnswerRequest
from app.services.llm.factory import get_llm_provider, reset_llm_provider_cache


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    reset_llm_provider_cache()
    yield
    reset_llm_provider_cache()


def _azure_settings(**overrides) -> Settings:
    base = dict(
        llm_provider="azure",
        azure_openai_endpoint="https://unit-test.openai.azure.com",
        azure_openai_api_key="test-key",
        azure_openai_chat_deployment="chat-deploy",
        azure_openai_embedding_deployment="embed-deploy",
        azure_openai_api_version="2024-10-21",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.mark.asyncio
async def test_embed_calls_azure_deployment():
    settings = _azure_settings()
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[MagicMock(embedding=[0.1, 0.2])])
    )
    with patch("app.services.llm.azure_openai.AsyncAzureOpenAI", return_value=mock_client):
        provider = AzureOpenAIProvider(settings)
        vectors = await provider.embed(["hello"])
    assert vectors == [[0.1, 0.2]]
    mock_client.embeddings.create.assert_awaited_once()
    assert mock_client.embeddings.create.await_args.kwargs["model"] == "embed-deploy"


@pytest.mark.asyncio
async def test_generate_answer_parses_json():
    settings = _azure_settings()
    payload = {
        "answer": "Yes, data is encrypted.",
        "confidence": "high",
        "evidence_ids": ["11111111-1111-4111-8111-111111111111"],
        "reasoning_summary": "Based on policy doc.",
        "evidence_sufficiency": "sufficient",
    }
    mock_message = MagicMock(content=json.dumps(payload))
    mock_choice = MagicMock(message=mock_message)
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=MagicMock(choices=[mock_choice]))
    with patch("app.services.llm.azure_openai.AsyncAzureOpenAI", return_value=mock_client):
        provider = AzureOpenAIProvider(settings)
        result = await provider.generate_answer(
            AnswerRequest(question="Encryption?", evidence_blocks=[{"id": "1", "content": "AES-256"}]),
        )
    assert result.answer == payload["answer"]
    assert result.evidence_sufficiency == "sufficient"
    assert mock_client.chat.completions.create.await_args.kwargs["model"] == "chat-deploy"


def test_factory_azure_requires_config():
    reset_llm_provider_cache()
    with patch("app.services.llm.factory.get_settings") as gs:
        gs.return_value = Settings(llm_provider="azure", azure_openai_endpoint=None)
        with pytest.raises(RuntimeError):
            get_llm_provider()

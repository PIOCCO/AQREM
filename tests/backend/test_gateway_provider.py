import json

import httpx
import pytest
from httpx import ASGITransport

from app.core.config import Settings, get_settings
from app.services.llm.base import AnswerRequest
from app.services.llm.errors import ModelServiceError
from app.services.llm.factory import get_llm_provider, reset_llm_provider_cache
from tests.backend.fake_gateway import VALID_KEY, STATE, app as fake_gateway_app


@pytest.fixture(autouse=True)
def _gateway_env(monkeypatch):
    STATE["mode"] = "ok"
    monkeypatch.setenv("LLM_PROVIDER", "gateway")
    monkeypatch.setenv("GATEWAY_URL", "http://gateway.test")
    monkeypatch.setenv("GATEWAY_API_KEY", VALID_KEY)
    get_settings.cache_clear()
    reset_llm_provider_cache()

    class _PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", ASGITransport(app=fake_gateway_app))
            kwargs.setdefault("base_url", "http://gateway.test")
            if "timeout" not in kwargs:
                kwargs["timeout"] = httpx.Timeout(30.0)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("app.services.llm.gateway.httpx.AsyncClient", _PatchedAsyncClient)
    yield
    reset_llm_provider_cache()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_gateway_embed_dimensions():
    settings = get_settings()
    provider = get_llm_provider()
    vectors = await provider.embed(["hello"])
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.embedding_dimensions


@pytest.mark.asyncio
async def test_gateway_generate_answer_json():
    provider = get_llm_provider()
    result = await provider.generate_answer(
        AnswerRequest(question="Q?", evidence_blocks=[{"id": "1", "content": "evidence"}]),
    )
    assert "Structured answer" in result.answer


@pytest.mark.asyncio
async def test_gateway_401_no_retry():
    STATE["mode"] = "401"
    provider = get_llm_provider()
    with pytest.raises(ModelServiceError) as exc:
        await provider.embed(["x"])
    assert exc.value.code == "gateway_unauthorized"


@pytest.mark.asyncio
async def test_gateway_429_user_message():
    STATE["mode"] = "429"
    provider = get_llm_provider()
    with pytest.raises(ModelServiceError) as exc:
        await provider.embed(["x"])
    assert exc.value.code == "gateway_rate_limit"


@pytest.mark.asyncio
async def test_gateway_stream_tokens():
    from app.services.llm.gateway import GatewayLLMProvider

    settings = get_settings()
    provider = GatewayLLMProvider(settings, api_key=VALID_KEY)
    parts: list[str] = []
    async for token in provider.stream_chat_tokens(
        messages=[{"role": "user", "content": "hi"}],
    ):
        parts.append(token)
    assert "".join(parts) == "Hello world"

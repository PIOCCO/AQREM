"""Azure OpenAI provider with a mocked HTTP layer (no real Azure credentials are used)."""

from __future__ import annotations

import json
import logging
import uuid
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.core.llm_config import validate_llm_startup
from app.services.llm.azure_openai import AzureOpenAIProvider
from app.services.llm.base import AnswerRequest
from app.services.llm.errors import (
    ASSISTANT_UNAVAILABLE_MESSAGE,
    EmbeddingDimensionMismatchError,
    ModelServiceError,
)
from app.services.llm.prompts import CHAT_STREAM_SYSTEM, SYSTEM_PROMPT

SECRET = "sk-test-secret-value-never-logged"


def _settings(**overrides) -> Settings:
    base = dict(
        llm_provider="azure",
        azure_openai_endpoint="https://unit-test.openai.azure.com",
        azure_openai_api_key=SECRET,
        azure_openai_chat_deployment="aqrem-chat",
        azure_openai_embedding_deployment="aqrem-embeddings",
        azure_openai_api_version="2024-10-21",
        embedding_dimensions=4,
        llm_max_retries=3,
    )
    base.update(overrides)
    return Settings(**base)


class Recorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        nxt = self.responses.pop(0)
        return nxt(request) if callable(nxt) else nxt


def _provider(handler, settings=None, sleeps=None):
    sleeps = sleeps if sleeps is not None else []

    async def fake_sleep(sec):
        sleeps.append(sec)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AzureOpenAIProvider(settings or _settings(), http_client=client, sleep=fake_sleep)


def _chat_ok(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
        },
    )


def _embed_ok(dim: int = 4, n: int = 1) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "object": "list",
            "model": "text-embedding-3-small",
            "data": [{"object": "embedding", "index": i, "embedding": [0.1] * dim} for i in range(n)],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        },
    )


def _err(status: int, code: str, message: str, headers=None) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": message}}, headers=headers or {})


@pytest.mark.asyncio
async def test_embeddings_success_uses_deployment_name_and_dimensions():
    rec = Recorder([_embed_ok(4, 2)])
    vectors = await _provider(rec).embed(["a", "b"])
    assert vectors == [[0.1] * 4, [0.1] * 4]
    req = rec.requests[0]
    assert "/openai/deployments/aqrem-embeddings/embeddings" in str(req.url)
    assert "api-version=2024-10-21" in str(req.url)
    assert req.headers["api-key"] == SECRET
    assert json.loads(req.content)["dimensions"] == 4


@pytest.mark.asyncio
async def test_chat_success_uses_chat_deployment_and_low_temperature():
    payload = {"answer": "AES-256 (Policy.pdf, p. 2)", "confidence": "high", "evidence_ids": ["e1"],
               "reasoning_summary": "", "evidence_sufficiency": "sufficient"}
    rec = Recorder([_chat_ok(json.dumps(payload))])
    result = await _provider(rec).generate_answer(
        AnswerRequest(question="Encryption?", evidence_blocks=[{"id": "e1", "document": "Policy.pdf", "page": 2,
                                                                "content": "AES-256"}])
    )
    assert result.answer.startswith("AES-256")
    req = rec.requests[0]
    assert "/openai/deployments/aqrem-chat/chat/completions" in str(req.url)
    body = json.loads(req.content)
    assert body["temperature"] == pytest.approx(0.1)
    assert body["messages"][0]["content"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_401_maps_to_wrong_key_without_leaking_secret(caplog):
    caplog.set_level(logging.DEBUG)
    rec = Recorder([_err(401, "401", "Access denied due to invalid subscription key.")])
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_unauthorized"
    assert ei.value.user_message == ASSISTANT_UNAVAILABLE_MESSAGE
    assert "AZURE_OPENAI_API_KEY" in ei.value.admin_message
    assert len(rec.requests) == 1  # not retried
    assert SECRET not in caplog.text


@pytest.mark.asyncio
async def test_deployment_not_found():
    rec = Recorder([_err(404, "DeploymentNotFound", "The API deployment for this resource does not exist.")])
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).chat_text([{"role": "user", "content": "hi"}])
    assert ei.value.code == "azure_deployment_not_found"
    assert "aqrem-chat" in ei.value.admin_message
    assert "DeploymentNotFound" in ei.value.admin_message


@pytest.mark.asyncio
async def test_404_without_deployment_is_wrong_endpoint():
    rec = Recorder([httpx.Response(404, json={"error": {"code": "404", "message": "Resource not found"}})])
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_endpoint_not_found"


@pytest.mark.asyncio
async def test_429_is_retried_honouring_retry_after_then_succeeds():
    sleeps: list[float] = []
    rec = Recorder([
        _err(429, "429", "Rate limit is exceeded.", headers={"retry-after": "7"}),
        _err(429, "429", "Rate limit is exceeded.", headers={"retry-after": "2"}),
        _embed_ok(4),
    ])
    vectors = await _provider(rec, sleeps=sleeps).embed(["x"])
    assert len(vectors) == 1
    assert len(rec.requests) == 3
    assert sleeps == [7.0, 2.0]


@pytest.mark.asyncio
async def test_429_exhausted_gives_rate_limit_error():
    rec = Recorder([_err(429, "429", "Rate limit is exceeded.", headers={"retry-after": "0"})] * 4)
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_rate_limited"
    assert ei.value.retryable
    assert len(rec.requests) == 4  # 1 + LLM_MAX_RETRIES


@pytest.mark.asyncio
async def test_quota_exceeded_message():
    rec = Recorder([_err(429, "insufficient_quota", "You exceeded your current quota.", {"retry-after": "0"})] * 4)
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_quota_exceeded"


@pytest.mark.asyncio
async def test_5xx_retried_with_backoff():
    sleeps: list[float] = []
    rec = Recorder([httpx.Response(503, json={"error": {"code": "x", "message": "busy"}}), _embed_ok(4)])
    await _provider(rec, sleeps=sleeps).embed(["x"])
    assert len(sleeps) == 1 and sleeps[0] >= 1.0


@pytest.mark.asyncio
async def test_unsupported_model_message():
    rec = Recorder([_err(400, "OperationNotSupported", "The embeddings operation does not work with the specified model.")])
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_unsupported_model"


@pytest.mark.asyncio
async def test_dns_failure_is_wrong_endpoint():
    def boom(request):
        raise httpx.ConnectError("[Errno -2] Name or service not known")

    rec = Recorder([boom])
    with pytest.raises(ModelServiceError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.code == "azure_endpoint_unreachable"
    assert len(rec.requests) == 1


@pytest.mark.asyncio
async def test_embedding_dimension_mismatch_detected():
    rec = Recorder([_embed_ok(1536)])
    with pytest.raises(EmbeddingDimensionMismatchError) as ei:
        await _provider(rec).embed(["x"])
    assert ei.value.expected == 4 and ei.value.actual == 1536
    assert "EMBEDDING_DIMENSIONS" in ei.value.admin_message


@pytest.mark.asyncio
async def test_test_connection_reports_each_check():
    rec = Recorder([_chat_ok("OK"), _err(404, "DeploymentNotFound", "deployment missing")])
    report = await _provider(rec).test_connection()
    assert report["chat"]["ok"] is True
    assert report["embeddings"]["ok"] is False
    assert report["embeddings"]["code"] == "azure_deployment_not_found"
    assert report["ok"] is False
    assert SECRET not in json.dumps(report)


# --- configuration validation -------------------------------------------------


def test_missing_var_gives_clear_error_naming_variable():
    s = _settings(azure_openai_chat_deployment="")
    with pytest.raises(RuntimeError) as ei:
        validate_llm_startup(s)
    assert "AZURE_OPENAI_CHAT_DEPLOYMENT" in str(ei.value)
    assert SECRET not in str(ei.value)


def test_missing_dimensions_is_required_for_azure():
    s = Settings(
        llm_provider="azure",
        azure_openai_endpoint="https://x.openai.azure.com",
        azure_openai_api_key=SECRET,
        azure_openai_chat_deployment="c",
        azure_openai_embedding_deployment="e",
    )
    with pytest.raises(RuntimeError, match="EMBEDDING_DIMENSIONS"):
        validate_llm_startup(s)


def test_blank_dimensions_env_treated_as_missing(monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "")
    s = Settings(llm_provider="azure")
    assert s.embedding_dimensions == 0


def test_production_missing_key_fails_fast_without_secret():
    with pytest.raises(ValueError) as ei:
        Settings(
            app_env="production",
            secret_key="x" * 40,
            llm_provider="azure",
            azure_openai_endpoint="https://x.openai.azure.com",
            azure_openai_chat_deployment="c",
            azure_openai_embedding_deployment="e",
            embedding_dimensions=1536,
            azure_storage_connection_string="UseDevelopmentStorage=true",
        )
    assert "AZURE_OPENAI_API_KEY" in str(ei.value)


def test_production_refuses_mock():
    with pytest.raises(ValueError, match="refuses to start with a mock"):
        Settings(app_env="production", secret_key="x" * 40, llm_provider="mock")


def test_production_accepts_complete_azure():
    s = Settings(
        app_env="production",
        secret_key="x" * 40,
        llm_provider="azure",
        azure_openai_endpoint="https://x.openai.azure.com",
        azure_openai_api_key=SECRET,
        azure_openai_chat_deployment="c",
        azure_openai_embedding_deployment="e",
        embedding_dimensions=1536,
        azure_storage_connection_string="UseDevelopmentStorage=true",
    )
    validate_llm_startup(s)


# --- embedding consistency ----------------------------------------------------


def test_document_embedding_mismatch_flag():
    from app.services.ingestion.embedding_health import document_embedding_mismatch

    doc = SimpleNamespace(status="indexed", embedding_model="azure:old:1536", embedding_dimensions=1536)
    assert document_embedding_mismatch(doc, "azure:aqrem-embeddings:1536", 1536)
    doc.embedding_model = "azure:aqrem-embeddings:1536"
    assert not document_embedding_mismatch(doc, "azure:aqrem-embeddings:1536", 1536)
    assert document_embedding_mismatch(doc, "azure:aqrem-embeddings:1536", 3072)


def test_vector_column_mismatch_message_and_detection():
    from app.services.ingestion import vector_schema

    class FakeConn:
        def execute(self, *_a, **_k):
            return SimpleNamespace(first=lambda: (384,))

    found = vector_schema.find_vector_mismatches(FakeConn(), 1536)
    assert found and found[0][2] == 384
    msg = vector_schema.vector_mismatch_message("evidence_items", "embedding", 384, 1536)
    assert "vector(384)" in msg and "EMBEDDING_DIMENSIONS=1536" in msg and "ALTER TABLE" in msg


# --- grounded prompt ----------------------------------------------------------


def test_system_prompts_are_grounded():
    for prompt in (SYSTEM_PROMPT, CHAT_STREAM_SYSTEM):
        assert "ONLY" in prompt
        assert "couldn't find this in the available documents" in prompt
        assert "page" in prompt.lower()
    assert "invent" in SYSTEM_PROMPT.lower()


def test_evidence_blocks_carry_document_and_page_and_answer_has_sources():
    from app.services.rag.grounding import append_source_references, evidence_blocks

    item = SimpleNamespace(
        id=uuid.uuid4(), file_name="Security Policy.pdf", file_path="Security Policy.pdf", line_start=1,
        line_end=5, repository=None, commit_hash=None, content="AES-256 at rest", evidence_strength="strong",
        item_metadata={"page": 3},
    )
    block = evidence_blocks([item])[0]
    assert block["document"] == "Security Policy.pdf" and block["page"] == 3
    out = append_source_references("Data is encrypted with AES-256.", [item], {item.id})
    assert out.endswith("Sources: Security Policy.pdf, p. 3")


def test_pdf_page_numbers_per_chunk():
    from app.services.ingestion.chunking import chunk_text, page_break_lines, page_for_line
    from app.services.ingestion.parsers import PDF_PAGE_BREAK

    text = PDF_PAGE_BREAK.join(["page one text\n" * 3, "page two text\n" * 3, "page three\n"])
    breaks = page_break_lines(text)
    chunks = chunk_text(text, max_chars=40, overlap=0)
    pages = [page_for_line(breaks, c.line_start) for c in chunks]
    assert pages[0] == 1 and pages[-1] == 3
    assert sorted(set(pages)) == [1, 2, 3]

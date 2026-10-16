"""Azure OpenAI chat + embeddings (deployment names from env, never model names).

Retries 429 / 5xx / timeouts with exponential backoff and honours ``Retry-After``.
Errors are logged with a readable classification (never the API key) and re-raised
as :class:`ModelServiceError` whose ``user_message`` is the employee-safe text and
whose ``admin_message`` explains the likely fix.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAzureOpenAI,
)

from app.core.config import Settings
from app.core.llm_config import require_azure_openai
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer
from app.services.llm.errors import (
    ASSISTANT_UNAVAILABLE_MESSAGE,
    EmbeddingDimensionMismatchError,
    ModelServiceError,
)
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger("aqrem.providers.azure")

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
_BASE_BACKOFF_SEC = 1.0
_MAX_BACKOFF_SEC = 20.0


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    for name in ("retry-after-ms", "x-ms-retry-after-ms"):
        raw = headers.get(name)
        if raw:
            try:
                return max(0.0, float(raw) / 1000.0)
            except ValueError:
                pass
    raw = headers.get("retry-after")
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            return None
    return None


def _error_code_and_text(exc: Exception) -> tuple[str, str]:
    body = getattr(exc, "body", None)
    code = ""
    message = ""
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict):
            code = str(inner.get("code") or "")
            message = str(inner.get("message") or "")
    if not code:
        code = str(getattr(exc, "code", "") or "")
    if not message:
        message = str(getattr(exc, "message", "") or str(exc))
    return code, message


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError)):
        # DNS failures are not transient; everything else (resets, timeouts) is.
        return not _is_dns_failure(exc)
    status = getattr(exc, "status_code", None)
    return status == 429 or (isinstance(status, int) and status >= 500)


def _is_dns_failure(exc: BaseException) -> bool:
    seen = 0
    cur: BaseException | None = exc
    while cur is not None and seen < 6:
        text = str(cur).lower()
        if "name or service not known" in text or "nodename nor servname" in text or "getaddrinfo" in text \
                or "temporary failure in name resolution" in text or "no address associated" in text:
            return True
        cur = cur.__cause__ or cur.__context__
        seen += 1
    return False


def classify_azure_error(exc: Exception, *, operation: str, deployment: str) -> ModelServiceError:
    """Map an SDK / transport error to a readable ModelServiceError (no secrets)."""
    status = getattr(exc, "status_code", None)
    code, detail = _error_code_and_text(exc)
    code_l = code.lower()
    detail_l = detail.lower()

    def _err(err_code: str, admin: str, http_status: int | None, retryable: bool) -> ModelServiceError:
        return ModelServiceError(
            code=err_code,
            user_message=ASSISTANT_UNAVAILABLE_MESSAGE,
            admin_message=admin,
            status_code=http_status,
            retryable=retryable,
        )

    if isinstance(exc, (APIConnectionError, APITimeoutError)) and status is None:
        if _is_dns_failure(exc):
            return _err(
                "azure_endpoint_unreachable",
                "Wrong endpoint: the host in AZURE_OPENAI_ENDPOINT could not be resolved (DNS). "
                "Copy the endpoint from Azure portal > your OpenAI resource > Keys and Endpoint.",
                None,
                False,
            )
        if isinstance(exc, APITimeoutError):
            return _err("azure_timeout", f"Azure OpenAI {operation} timed out.", 504, True)
        return _err(
            "azure_connection_error",
            "Could not connect to AZURE_OPENAI_ENDPOINT (network error). Check the URL and outbound internet access.",
            503,
            True,
        )
    if status == 401 or status == 403:
        return _err(
            "azure_unauthorized",
            "Wrong key (HTTP %s): AZURE_OPENAI_API_KEY was rejected. Use KEY 1 or KEY 2 from the same "
            "resource as AZURE_OPENAI_ENDPOINT." % status,
            status,
            False,
        )
    if code_l == "deploymentnotfound" or (status == 404 and "deployment" in detail_l):
        return _err(
            "azure_deployment_not_found",
            f"Deployment not found (DeploymentNotFound): '{deployment}' does not exist on this resource. "
            "Set the deployment *name* you created in Azure AI Foundry (not the model name), "
            "or wait a few minutes after creating it.",
            404,
            False,
        )
    if status == 404:
        return _err(
            "azure_endpoint_not_found",
            "Wrong endpoint (HTTP 404): AZURE_OPENAI_ENDPOINT should look like "
            "https://<resource>.openai.azure.com/ with nothing after the host. Also check AZURE_OPENAI_API_VERSION.",
            404,
            False,
        )
    if status == 429:
        quota = "quota" in detail_l or "insufficient_quota" in code_l
        return _err(
            "azure_quota_exceeded" if quota else "azure_rate_limited",
            ("Quota exceeded (HTTP 429): raise the deployment's tokens-per-minute quota in Azure."
             if quota else
             "Rate limit (HTTP 429): too many requests for this deployment's TPM/RPM quota; retry later or raise quota."),
            429,
            True,
        )
    if status == 400 and (
        "operationnotsupported" in code_l
        or "unsupported" in detail_l
        or "does not work with the specified model" in detail_l
        or "model" in code_l
    ):
        return _err(
            "azure_unsupported_model",
            "The deployment's model does not support this operation or is not available in this region "
            f"({code or 'HTTP 400'}). Use a chat model (e.g. gpt-4o-mini) for AZURE_OPENAI_CHAT_DEPLOYMENT and an "
            "embedding model (e.g. text-embedding-3-small) for AZURE_OPENAI_EMBEDDING_DEPLOYMENT, "
            "in a region that offers them.",
            400,
            False,
        )
    if isinstance(status, int) and status >= 500:
        return _err("azure_upstream_error", f"Azure OpenAI returned HTTP {status}.", status, True)
    return _err(
        "azure_error",
        f"Azure OpenAI {operation} failed ({code or 'HTTP ' + str(status)}).",
        status or 502,
        False,
    )


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI chat + embeddings via the official OpenAI Python SDK."""

    provider_name = "azure"

    def __init__(self, settings: Settings, *, http_client: httpx.AsyncClient | None = None,
                 sleep: Any = None) -> None:
        require_azure_openai(settings)
        self.settings = settings
        self._sleep = sleep or asyncio.sleep
        self._client = self._build_client(settings, http_client=http_client)

    @property
    def chat_model_id(self) -> str:
        return f"azure:{self.settings.azure_openai_chat_deployment}"

    @property
    def embedding_model_id(self) -> str:
        return f"azure:{self.settings.azure_openai_embedding_deployment}:{self.settings.embedding_dimensions}"

    @staticmethod
    def _build_client(settings: Settings, *, http_client: httpx.AsyncClient | None = None) -> AsyncAzureOpenAI:
        endpoint = (settings.azure_openai_endpoint or "").rstrip("/")
        common: dict[str, Any] = {
            "azure_endpoint": endpoint,
            "api_version": settings.azure_openai_api_version,
            "max_retries": 0,  # we retry ourselves (honouring Retry-After)
            "timeout": 60.0,
        }
        if http_client is not None:
            common["http_client"] = http_client
        if settings.azure_openai_use_managed_identity:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, _COGNITIVE_SCOPE)
            return AsyncAzureOpenAI(azure_ad_token_provider=token_provider, **common)
        return AsyncAzureOpenAI(api_key=settings.azure_openai_api_key, **common)

    async def _with_retries(self, op_name: str, deployment: str, coro_factory: Any) -> Any:
        attempts = max(1, int(self.settings.llm_max_retries) + 1)
        for attempt in range(attempts):
            try:
                return await coro_factory()
            except (APIStatusError, APIConnectionError, APITimeoutError) as exc:
                retryable = is_retryable(exc)
                if retryable and attempt < attempts - 1:
                    delay = _retry_after_seconds(exc)
                    if delay is None:
                        delay = min(_MAX_BACKOFF_SEC, _BASE_BACKOFF_SEC * (2**attempt)) + random.uniform(0, 0.25)
                    delay = min(delay, 60.0)
                    logger.warning(
                        "Azure OpenAI %s transient failure deployment=%s status=%s (attempt %s/%s); retrying in %.1fs",
                        op_name, deployment, getattr(exc, "status_code", None), attempt + 1, attempts, delay,
                    )
                    await self._sleep(delay)
                    continue
                mapped = classify_azure_error(exc, operation=op_name, deployment=deployment)
                logger.error(
                    "Azure OpenAI %s failed deployment=%s code=%s status=%s: %s",
                    op_name, deployment, mapped.code, mapped.status_code, mapped.admin_message,
                )
                raise mapped from exc
        raise RuntimeError("unreachable")  # pragma: no cover

    async def embed(self, texts: list[str]) -> list[list[float]]:
        deployment = self.settings.azure_openai_embedding_deployment
        expected = self.settings.embedding_dimensions

        extra: dict[str, Any] = {}
        if self.settings.azure_openai_embedding_send_dimensions:
            # text-embedding-3-* honour this; set AZURE_OPENAI_EMBEDDING_SEND_DIMENSIONS=false for ada-002.
            extra["dimensions"] = expected

        async def _call():
            response = await self._client.embeddings.create(model=deployment, input=texts, **extra)
            return [item.embedding for item in response.data]

        vectors = await self._with_retries("embeddings", deployment, _call)
        for vec in vectors:
            if len(vec or []) != expected:
                logger.error(
                    "Azure embedding deployment=%s returned %s dimensions but EMBEDDING_DIMENSIONS=%s",
                    deployment, len(vec or []), expected,
                )
                raise EmbeddingDimensionMismatchError(expected=expected, actual=len(vec or []))
        return vectors

    async def chat_text(self, messages: list[dict], *, max_tokens: int | None = None,
                        json_mode: bool = False) -> str:
        deployment = self.settings.azure_openai_chat_deployment
        kwargs: dict[str, Any] = {
            "model": deployment,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": max_tokens or self.settings.llm_max_output_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        async def _call():
            return await self._client.chat.completions.create(**kwargs)

        response = await self._with_retries("chat.completions", deployment, _call)
        return response.choices[0].message.content or ""

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        user_content = json.dumps(
            {
                "question": request.question,
                "evidence": request.evidence_blocks,
                "extra_instructions": request.instructions,
            }
        )
        content = await self.chat_text(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            json_mode=True,
        )
        try:
            parsed = json.loads(content or "{}")
        except json.JSONDecodeError:
            logger.warning("Azure chat returned non-JSON content; treating as plain answer")
            parsed = {"answer": content, "confidence": "low", "evidence_sufficiency": "insufficient"}
        return StructuredAnswer(
            answer=parsed.get("answer", ""),
            confidence=parsed.get("confidence", "low"),
            evidence_ids=[str(x) for x in parsed.get("evidence_ids", [])],
            reasoning_summary=parsed.get("reasoning_summary", ""),
            evidence_sufficiency=parsed.get("evidence_sufficiency", "insufficient"),
        )

    async def test_connection(self) -> dict:
        """One tiny chat + one tiny embedding call. Returns a readable report (no secrets)."""
        result: dict[str, Any] = {
            "provider": "azure",
            "endpoint_host": (self.settings.azure_openai_endpoint or "").split("//")[-1].split("/")[0],
            "api_version": self.settings.azure_openai_api_version,
            "chat_deployment": self.settings.azure_openai_chat_deployment,
            "embedding_deployment": self.settings.azure_openai_embedding_deployment,
            "embedding_dimensions": self.settings.embedding_dimensions,
        }
        try:
            await self.chat_text([{"role": "user", "content": "Reply with the word OK."}], max_tokens=5)
            result["chat"] = {"ok": True, "message": "Chat deployment responded."}
        except ModelServiceError as exc:
            result["chat"] = {"ok": False, "code": exc.code, "message": exc.admin_message}
        try:
            vecs = await self.embed(["connection test"])
            result["embeddings"] = {"ok": True, "message": f"Embedding deployment returned {len(vecs[0])} dimensions."}
        except ModelServiceError as exc:
            result["embeddings"] = {"ok": False, "code": exc.code, "message": exc.admin_message}
        result["ok"] = bool(result["chat"]["ok"] and result["embeddings"]["ok"])
        return result

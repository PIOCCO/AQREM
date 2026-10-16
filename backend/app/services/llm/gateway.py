"""Model gateway client — OpenAI-compatible paths via AQREM gateway aliases."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.core.gateway_config import require_gateway
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer
from app.services.llm.errors import ModelServiceError
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = (0.5, 1.5, 3.0)
_RETRY_AFTER_CAP_SEC = 120


def _jitter_delay(base: float) -> float:
    return base * (0.85 + random.random() * 0.3)


class GatewayLLMProvider(LLMProvider):
    provider_name = "gateway"

    def __init__(self, settings: Settings, *, api_key: str) -> None:
        require_gateway(settings)
        self.settings = settings
        self.api_key = api_key
        self._timeout = httpx.Timeout(settings.gateway_timeout_seconds)

    @property
    def chat_model_id(self) -> str:
        return f"gateway:{self.settings.gateway_chat_alias}"

    @property
    def embedding_model_id(self) -> str:
        return f"gateway:{self.settings.gateway_embeddings_alias}:{self.settings.embedding_dimensions}"

    def _base_url(self) -> str:
        return (self.settings.gateway_url or "").rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat_path(self) -> str:
        alias = self.settings.gateway_chat_alias
        return f"/v1/{alias}/chat/completions"

    def _embed_path(self) -> str:
        alias = self.settings.gateway_embeddings_alias
        return f"/v1/{alias}/embeddings"

    def _map_http_error(self, status: int, body: str) -> ModelServiceError:
        detail = ""
        try:
            parsed = json.loads(body)
            detail = str(parsed.get("message") or parsed.get("detail") or "")
            err_code = str(parsed.get("code") or "")
        except json.JSONDecodeError:
            detail = ""
            err_code = ""
        lower = detail.lower()
        if status == 401:
            return ModelServiceError(
                code="gateway_unauthorized",
                user_message="The model connection is not authorized. Contact your organization administrator.",
                status_code=401,
                retryable=False,
            )
        if status == 429 and err_code == "monthly_token_budget_exceeded":
            return ModelServiceError(
                code="monthly_token_budget_exceeded",
                user_message=(
                    "Your organization's monthly model token budget has been reached. "
                    "Ask an organization administrator to review usage or request a limit increase."
                ),
                status_code=429,
                retryable=False,
            )
        if status == 429 or "budget" in lower or "rate limit" in lower:
            return ModelServiceError(
                code="gateway_rate_limit",
                user_message=(
                    "The model is temporarily busy. Try again shortly."
                ),
                status_code=429,
                retryable=True,
            )
        if status >= 500:
            return ModelServiceError(
                code="gateway_upstream",
                user_message="The model service is temporarily unavailable. Please try again.",
                status_code=status,
                retryable=True,
            )
        return ModelServiceError(
            code="gateway_error",
            user_message="We couldn't complete the model request. Please try again.",
            status_code=status,
            retryable=False,
        )

    async def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        op_name: str,
        retry_on_401: bool = False,
    ) -> dict[str, Any]:
        url = f"{self._base_url()}{path}"
        last_error: ModelServiceError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, headers=self._headers(), json=payload)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                logger.warning(
                    "gateway %s connection error attempt=%s type=%s",
                    op_name,
                    attempt + 1,
                    type(exc).__name__,
                )
                if attempt >= _MAX_ATTEMPTS - 1:
                    raise ModelServiceError(
                        code="gateway_timeout",
                        user_message="The model request timed out. Please try again.",
                        retryable=True,
                    ) from exc
                await asyncio.sleep(_jitter_delay(_BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)]))
                continue

            if resp.status_code == 401 and not retry_on_401:
                raise self._map_http_error(resp.status_code, resp.text)

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS - 1:
                last_error = self._map_http_error(resp.status_code, resp.text)
                retry_after: float | None = None
                if resp.status_code == 429:
                    raw = resp.headers.get("Retry-After")
                    if raw and raw.isdigit():
                        retry_after = min(float(raw), _RETRY_AFTER_CAP_SEC)
                delay = retry_after if retry_after is not None else _BACKOFF_BASE[min(attempt, len(_BACKOFF_BASE) - 1)]
                logger.warning(
                    "gateway %s retryable status=%s attempt=%s delay=%s",
                    op_name,
                    resp.status_code,
                    attempt + 1,
                    delay,
                )
                await asyncio.sleep(_jitter_delay(delay))
                continue

            if resp.status_code >= 400:
                raise self._map_http_error(resp.status_code, resp.text)

            return resp.json()

        assert last_error is not None
        raise last_error

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = await self._post_json(
            self._embed_path(),
            {"input": texts},
            op_name="embeddings",
        )
        rows = data.get("data") or []
        return [row.get("embedding") or [] for row in rows]

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        user_content = json.dumps(
            {
                "question": request.question,
                "evidence": request.evidence_blocks,
                "extra_instructions": request.instructions,
            }
        )
        data = await self._post_json(
            self._chat_path(),
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.1,
                "max_tokens": self.settings.llm_max_output_tokens,
                "response_format": {"type": "json_object"},
            },
            op_name="chat.completions",
        )
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}"
        parsed = json.loads(content)
        finish = ((data.get("choices") or [{}])[0].get("finish_reason")) or ""
        answer_text = str(parsed.get("answer", ""))
        if finish == "length" and answer_text:
            answer_text = answer_text.rstrip() + "\n\n[Answer may be incomplete — try asking to continue.]"
        return StructuredAnswer(
            answer=answer_text,
            confidence=parsed.get("confidence", "low"),
            evidence_ids=[str(x) for x in parsed.get("evidence_ids", [])],
            reasoning_summary=parsed.get("reasoning_summary", ""),
            evidence_sufficiency=parsed.get("evidence_sufficiency", "insufficient"),
        )

    async def stream_chat_tokens(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream delta content tokens from chat-default."""
        url = f"{self._base_url()}{self._chat_path()}"
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens or self.settings.llm_max_output_tokens,
            "stream": True,
        }
        attempt = 0
        while attempt < _MAX_ATTEMPTS:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST", url, headers=self._headers(), json=payload
                    ) as resp:
                        if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_ATTEMPTS:
                            body = await resp.aread()
                            err = self._map_http_error(resp.status_code, body.decode("utf-8", errors="replace"))
                            if err.retryable:
                                await asyncio.sleep(_jitter_delay(_BACKOFF_BASE[min(attempt - 1, 2)]))
                                continue
                            raise err
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            raise self._map_http_error(
                                resp.status_code, body.decode("utf-8", errors="replace")
                            )
                        async for line in resp.aiter_lines():
                            if cancel_event and cancel_event.is_set():
                                await resp.aclose()
                                return
                            if not line or not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue
                            choices = chunk.get("choices") or []
                            if not choices:
                                continue
                            delta = (choices[0].get("delta") or {}).get("content")
                            if delta:
                                yield str(delta)
                return
            except ModelServiceError:
                raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempt >= _MAX_ATTEMPTS:
                    raise ModelServiceError(
                        code="gateway_stream_interrupted",
                        user_message="The answer stream was interrupted. You can retry your question.",
                        retryable=True,
                    ) from exc
                await asyncio.sleep(_jitter_delay(_BACKOFF_BASE[min(attempt - 1, 2)]))
        return


_EVIDENCE_ID_IN_TEXT = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)


def evidence_ids_mentioned(text: str, allowed: set[str]) -> list[str]:
    seen: list[str] = []
    for match in _EVIDENCE_ID_IN_TEXT.findall(text):
        mid = match.lower()
        if mid in allowed and mid not in seen:
            seen.append(mid)
    return seen

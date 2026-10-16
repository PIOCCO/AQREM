"""Direct OpenAI chat and embeddings (API key from the environment)."""

from __future__ import annotations

import json
import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import Settings
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer
from app.services.llm.errors import EmbeddingDimensionMismatchError, ModelServiceError
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Real OpenAI models. Indexing and querying share this client and embedding size."""

    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise RuntimeError("LLM_PROVIDER=openai requires OPENAI_API_KEY.")
        self.settings = settings
        self._client = AsyncOpenAI(
            api_key=key,
            base_url=(settings.openai_base_url or "https://api.openai.com/v1").rstrip("/"),
        )

    @property
    def chat_model_id(self) -> str:
        return f"openai:{self.settings.openai_chat_model}"

    @property
    def embedding_model_id(self) -> str:
        return (
            f"openai:{self.settings.openai_embedding_model}:{self.settings.embedding_dimensions}"
        )

    def _supports_dimensions(self) -> bool:
        return self.settings.openai_embedding_model.startswith("text-embedding-3")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        kwargs: dict = {
            "model": self.settings.openai_embedding_model,
            "input": texts,
        }
        if self._supports_dimensions():
            kwargs["dimensions"] = self.settings.embedding_dimensions
        try:
            response = await self._client.embeddings.create(**kwargs)
        except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as exc:
            raise self._map_error(exc) from exc
        vectors = [list(item.embedding) for item in response.data]
        expected = self.settings.embedding_dimensions
        for vec in vectors:
            if len(vec) != expected:
                raise EmbeddingDimensionMismatchError(expected=expected, actual=len(vec))
        return vectors

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        user_content = json.dumps(
            {
                "question": request.question,
                "evidence": request.evidence_blocks,
                "extra_instructions": request.instructions,
            }
        )
        try:
            response = await self._client.chat.completions.create(
                model=self.settings.openai_chat_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=self.settings.llm_max_output_tokens,
                response_format={"type": "json_object"},
            )
        except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as exc:
            raise self._map_error(exc) from exc
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return StructuredAnswer(
            answer=parsed.get("answer", ""),
            confidence=parsed.get("confidence", "low"),
            evidence_ids=[str(x) for x in parsed.get("evidence_ids", [])],
            reasoning_summary=parsed.get("reasoning_summary", ""),
            evidence_sufficiency=parsed.get("evidence_sufficiency", "insufficient"),
        )

    def _map_error(self, exc: Exception) -> ModelServiceError:
        status = getattr(exc, "status_code", None)
        logger.warning("OpenAI request failed type=%s status=%s", type(exc).__name__, status)
        if status == 401:
            return ModelServiceError(
                code="openai_unauthorized",
                user_message="The model connection is not authorized. Contact your organization administrator.",
                status_code=401,
                retryable=False,
            )
        if status == 429 or isinstance(exc, RateLimitError):
            return ModelServiceError(
                code="openai_rate_limit",
                user_message="The model is temporarily busy. Try again shortly.",
                status_code=429,
                retryable=True,
            )
        if isinstance(exc, (APITimeoutError, APIConnectionError)) or (status or 0) >= 500:
            return ModelServiceError(
                code="openai_upstream",
                user_message="The model service is temporarily unavailable. Please try again.",
                status_code=status or 503,
                retryable=True,
            )
        return ModelServiceError(
            code="openai_error",
            user_message="We couldn't complete the model request. Please try again.",
            status_code=status or 502,
            retryable=False,
        )

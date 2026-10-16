import asyncio
import json
import logging
from typing import Any

from openai import APIConnectionError, APITimeoutError, AsyncAzureOpenAI, RateLimitError

from app.core.config import Settings
from app.core.llm_config import require_azure_openai
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer
from app.services.llm.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SEC = (0.5, 1.5, 3.0)


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI chat + embeddings via the official OpenAI Python SDK."""

    provider_name = "azure"

    def __init__(self, settings: Settings) -> None:
        require_azure_openai(settings)
        self.settings = settings
        self._client = self._build_client(settings)

    @property
    def chat_model_id(self) -> str:
        return f"azure:{self.settings.azure_openai_chat_deployment}"

    @property
    def embedding_model_id(self) -> str:
        return f"azure:{self.settings.azure_openai_embedding_deployment}:{self.settings.embedding_dimensions}"

    @staticmethod
    def _build_client(settings: Settings) -> AsyncAzureOpenAI:
        endpoint = (settings.azure_openai_endpoint or "").rstrip("/")
        api_version = settings.azure_openai_api_version
        if settings.azure_openai_use_managed_identity:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(credential, _COGNITIVE_SCOPE)
            return AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                azure_ad_token_provider=token_provider,
            )
        return AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=api_version,
        )

    async def _with_retries(self, op_name: str, coro_factory: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await coro_factory()
            except (RateLimitError, APITimeoutError, APIConnectionError) as exc:
                last_exc = exc
                if attempt >= _MAX_ATTEMPTS - 1:
                    break
                delay = _RETRY_BACKOFF_SEC[min(attempt, len(_RETRY_BACKOFF_SEC) - 1)]
                logger.warning(
                    "Azure OpenAI %s transient failure (attempt %s/%s): %s",
                    op_name,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    type(exc).__name__,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        deployment = self.settings.azure_openai_embedding_deployment

        async def _call():
            response = await self._client.embeddings.create(model=deployment, input=texts)
            return [item.embedding for item in response.data]

        return await self._with_retries("embeddings", _call)

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        deployment = self.settings.azure_openai_chat_deployment
        user_content = json.dumps(
            {
                "question": request.question,
                "evidence": request.evidence_blocks,
                "extra_instructions": request.instructions,
            }
        )

        async def _call():
            return await self._client.chat.completions.create(
                model=deployment,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_tokens=self.settings.llm_max_output_tokens,
                response_format={"type": "json_object"},
            )

        response = await self._with_retries("chat.completions", _call)
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return StructuredAnswer(
            answer=parsed.get("answer", ""),
            confidence=parsed.get("confidence", "low"),
            evidence_ids=[str(x) for x in parsed.get("evidence_ids", [])],
            reasoning_summary=parsed.get("reasoning_summary", ""),
            evidence_sufficiency=parsed.get("evidence_sufficiency", "insufficient"),
        )

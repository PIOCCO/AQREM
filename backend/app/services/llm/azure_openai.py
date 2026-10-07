import json
from typing import Any

import httpx

from app.core.config import Settings
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer
from app.services.llm.prompts import SYSTEM_PROMPT

_COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = settings.azure_openai_endpoint.rstrip("/") if settings.azure_openai_endpoint else ""
        self.api_key = settings.azure_openai_api_key or ""
        self.api_version = settings.azure_openai_api_version
        self._credential: Any | None = None

    def _auth_headers(self) -> dict[str, str]:
        if self.settings.azure_openai_use_managed_identity:
            if self._credential is None:
                from azure.identity import DefaultAzureCredential

                self._credential = DefaultAzureCredential()
            token = self._credential.get_token(_COGNITIVE_SCOPE)
            return {"Authorization": f"Bearer {token.token}"}
        if self.api_key:
            return {"api-key": self.api_key}
        raise RuntimeError(
            "Azure OpenAI is not configured: set AZURE_OPENAI_API_KEY or AZURE_OPENAI_USE_MANAGED_IDENTITY=true",
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        url = (
            f"{self.base}/openai/deployments/{self.settings.azure_openai_embedding_deployment}"
            f"/embeddings?api-version={self.api_version}"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers=self._auth_headers(),
                json={"input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        url = (
            f"{self.base}/openai/deployments/{self.settings.azure_openai_chat_deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        user_content = json.dumps(
            {
                "question": request.question,
                "evidence": request.evidence_blocks,
                "extra_instructions": request.instructions,
            }
        )
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                url,
                headers=self._auth_headers(),
                json={
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.1,
                    "max_tokens": self.settings.llm_max_output_tokens,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return StructuredAnswer(
            answer=parsed.get("answer", ""),
            confidence=parsed.get("confidence", "low"),
            evidence_ids=[str(x) for x in parsed.get("evidence_ids", [])],
            reasoning_summary=parsed.get("reasoning_summary", ""),
            evidence_sufficiency=parsed.get("evidence_sufficiency", "insufficient"),
        )

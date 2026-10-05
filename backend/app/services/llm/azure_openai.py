import json

import httpx

from app.core.config import Settings
from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer

SYSTEM_PROMPT = """You are an evidence-backed questionnaire assistant for a company.
Rules:
1. Answer ONLY using the provided evidence blocks.
2. NEVER invent company-specific facts.
3. If evidence is insufficient, set evidence_sufficiency to "insufficient" and state that clearly.
4. Cite evidence by evidence id in evidence_ids.
5. Distinguish direct evidence from assumptions in reasoning_summary (brief, no hidden chain-of-thought).
6. Do not treat marketing language as technical proof.
7. Output valid JSON only with keys: answer, confidence, evidence_ids, reasoning_summary, evidence_sufficiency.
"""


class AzureOpenAIProvider(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = settings.azure_openai_endpoint.rstrip("/") if settings.azure_openai_endpoint else ""
        self.api_key = settings.azure_openai_api_key or ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        url = (
            f"{self.base}/openai/deployments/{self.settings.azure_openai_embedding_deployment}"
            f"/embeddings?api-version=2024-02-01"
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={"api-key": self.api_key},
                json={"input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data["data"]]

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        url = (
            f"{self.base}/openai/deployments/{self.settings.azure_openai_chat_deployment}"
            f"/chat/completions?api-version=2024-02-01"
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
                headers={"api-key": self.api_key},
                json={
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.1,
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

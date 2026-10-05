import hashlib
import math

from app.services.llm.base import AnswerRequest, LLMProvider, StructuredAnswer


class MockLLMProvider(LLMProvider):
    """Deterministic embeddings and placeholder answers for local dev/CI."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def _hash_embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for i in range(self.dimensions):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer:
        if not request.evidence_blocks:
            return StructuredAnswer(
                answer="Insufficient evidence: no supporting documents were retrieved for this question.",
                confidence="low",
                evidence_sufficiency="insufficient",
                reasoning_summary="No evidence blocks were provided to the model.",
            )
        cited_ids = [str(b.get("id", "")) for b in request.evidence_blocks[:3] if b.get("id")]
        snippets = []
        for block in request.evidence_blocks[:2]:
            path = block.get("file_path", "evidence")
            content = str(block.get("content", "")).strip().replace("\n", " ")
            if content:
                snippets.append(f"{path}: {content[:240]}")
        answer_text = (
            " ".join(snippets)
            if snippets
            else "Draft answer based on retrieved evidence (mock provider)."
        )
        return StructuredAnswer(
            answer=answer_text[:1500],
            confidence="high" if len(cited_ids) >= 2 else "medium",
            evidence_ids=cited_ids,
            evidence_sufficiency="sufficient",
            reasoning_summary="Answer synthesized strictly from retrieved evidence snippets.",
        )

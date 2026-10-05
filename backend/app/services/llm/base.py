from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StructuredAnswer:
    answer: str
    confidence: str
    evidence_ids: list[str] = field(default_factory=list)
    reasoning_summary: str = ""
    evidence_sufficiency: str = "insufficient"


@dataclass
class AnswerRequest:
    question: str
    evidence_blocks: list[dict]
    instructions: str = ""


class LLMProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def generate_answer(self, request: AnswerRequest) -> StructuredAnswer: ...

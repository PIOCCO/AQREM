from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceItemSummaryResponse


class ChatAskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    project_id: UUID | None = None


class ChatAskResponse(BaseModel):
    query: str
    answer: str
    confidence: str
    evidence_sufficiency: str
    reasoning_summary: str | None = None
    is_draft: bool = True
    from_library: bool = False
    library_entry_id: UUID | None = None
    citations: list[EvidenceItemSummaryResponse] = Field(default_factory=list)

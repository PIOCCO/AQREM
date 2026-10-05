from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LibraryEvidenceRef(BaseModel):
    evidence_item_id: UUID | None
    file_path: str
    snapshot_content_hash: str
    evidence_strength: str | None


class AnswerLibraryEntryResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    scope: str
    question_text: str
    normalized_question: str
    answer_text: str
    status: str
    version: int
    reuse_count: int
    approved_at: datetime | None
    evidence: list[LibraryEvidenceRef] = Field(default_factory=list)


class AnswerLibrarySearchRequest(BaseModel):
    query: str | None = None
    project_id: UUID | None = None
    limit: int = 50

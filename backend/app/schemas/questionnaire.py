from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionnaireCreate(BaseModel):
    name: str
    project_id: UUID | None = None
    recipient: str | None = None
    description: str | None = None


class QuestionnaireResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    name: str
    recipient: str | None
    description: str | None
    status: str
    question_count: int = 0
    created_at: datetime


class QuestionResponse(BaseModel):
    id: UUID
    questionnaire_id: UUID
    external_id: str
    section: str | None
    text: str
    sort_order: int


class EvidenceCitation(BaseModel):
    id: UUID
    file_name: str
    file_path: str
    line_start: int | None
    line_end: int | None
    repository: str | None
    commit_hash: str | None
    evidence_strength: str | None
    content_preview: str


class AnswerResponse(BaseModel):
    id: UUID
    question_id: UUID
    draft_text: str
    approved_text: str | None
    confidence: str
    evidence_sufficiency: str
    reasoning_summary: str | None
    status: str
    version: int
    potentially_stale: bool
    generation_source: str | None = None
    library_entry_id: UUID | None = None
    evidence: list[EvidenceCitation] = Field(default_factory=list)


class QuestionDetailResponse(BaseModel):
    question: QuestionResponse
    answer: AnswerResponse | None


class AnswerEditRequest(BaseModel):
    text: str = Field(min_length=1)


class GenerateBatchResponse(BaseModel):
    questionnaire_id: UUID
    generated: int
    insufficient: int

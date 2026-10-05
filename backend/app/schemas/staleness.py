from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChangedEvidenceItem(BaseModel):
    event_id: str
    file_path: str
    evidence_strength: str | None = None
    snapshot_content_hash: str
    current_content_hash: str
    previous_commit_hash: str | None = None
    current_commit_hash: str | None = None
    previous_content_excerpt: str | None = None
    current_content_excerpt: str | None = None
    detected_at: str
    reason: str
    source_id: str | None = None


class StaleAnswerSummary(BaseModel):
    answer_id: UUID
    question_id: UUID
    question_external_id: str
    question_text: str
    project_id: UUID | None
    project_name: str | None
    status: str
    potentially_stale: bool
    stale_detected_at: datetime | None
    stale_reason: str | None
    approved_text: str | None
    draft_text: str
    changed_evidence_count: int = 0


class StaleAnswerListResponse(BaseModel):
    items: list[StaleAnswerSummary]
    total: int
    offset: int
    limit: int


class StaleAnswerDetailResponse(BaseModel):
    answer_id: UUID
    question_id: UUID
    question_external_id: str
    question_text: str
    project_id: UUID | None
    project_name: str | None
    questionnaire_id: UUID
    questionnaire_name: str
    status: str
    potentially_stale: bool
    stale_reason: str | None
    approved_text: str | None
    draft_text: str
    generation_source: str | None
    changed_evidence: list[ChangedEvidenceItem] = Field(default_factory=list)
    library_entry_status: str | None = None


class RevalidateResponse(BaseModel):
    current: bool
    status: str
    potentially_stale: bool
    changed_evidence: list[dict] = Field(default_factory=list)

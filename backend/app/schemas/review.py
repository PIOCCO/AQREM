from uuid import UUID

from pydantic import BaseModel


class ReviewQueueItem(BaseModel):
    answer_id: UUID
    question_id: UUID
    question_external_id: str
    question_text: str
    questionnaire_id: UUID | None
    questionnaire_name: str | None
    project_id: UUID | None
    project_name: str | None
    status: str
    confidence: str
    evidence_sufficiency: str
    potentially_stale: bool
    reason: str


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    offset: int
    limit: int

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceItemSummaryResponse


class ChatAskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    project_id: UUID | None = None


class EvidenceConflictResponse(BaseModel):
    topic: str
    detail: str
    source_paths: list[str] = Field(default_factory=list)


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
    outcome: str = "answered"
    missing_information: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    needs_review: bool = False
    conflicts: list[EvidenceConflictResponse] = Field(default_factory=list)
    conversational: bool = False
    intent: str | None = None
    project_name: str | None = None
    sources_searched: int = 0
    query_time_ms: int | None = None


class ChatShareMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(max_length=32000)
    created_at: str | None = None


class CreateChatShareRequest(BaseModel):
    client_conversation_id: str = Field(min_length=1, max_length=64)
    title: str = Field(default="Shared conversation", max_length=200)
    messages: list[ChatShareMessage] = Field(default_factory=list, max_length=500)


class CreateChatShareResponse(BaseModel):
    share_token: str
    share_path: str


class ChatShareViewResponse(BaseModel):
    title: str
    messages: list[ChatShareMessage]
    shared_at: datetime

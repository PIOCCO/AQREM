from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EvidenceItemResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    source_id: UUID
    source_type: str
    scope: str
    file_name: str
    file_path: str
    content: str
    content_truncated: bool = False
    content_type: str
    language: str | None
    repository: str | None
    branch: str | None
    commit_hash: str | None
    line_start: int | None
    line_end: int | None
    symbol_name: str | None
    symbol_kind: str | None
    evidence_strength: str | None
    chunk_index: int
    created_at: datetime


class EvidenceItemSummaryResponse(BaseModel):
    """List view: same metadata as full item but content capped for browser/API performance."""

    id: UUID
    organization_id: UUID
    project_id: UUID | None
    source_id: UUID
    source_type: str
    scope: str
    file_name: str
    file_path: str
    content: str
    content_truncated: bool = False
    content_type: str
    language: str | None
    repository: str | None
    branch: str | None
    commit_hash: str | None
    line_start: int | None
    line_end: int | None
    symbol_name: str | None
    symbol_kind: str | None
    evidence_strength: str | None
    chunk_index: int
    created_at: datetime


class EvidenceListResponse(BaseModel):
    items: list[EvidenceItemSummaryResponse]
    total: int
    offset: int
    limit: int


class EvidenceSearchRequest(BaseModel):
    query: str
    project_id: UUID | None = None
    source_id: UUID | None = None
    limit: int = 8


class RetrievalPreviewResponse(BaseModel):
    query: str
    items: list[EvidenceItemResponse]

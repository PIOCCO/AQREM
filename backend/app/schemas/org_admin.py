from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ModelTokenSaveRequest(BaseModel):
    token: str = Field(min_length=8, max_length=4096)


class ModelTokenResponse(BaseModel):
    masked_value: str
    status: str
    expires_at: datetime | None
    last_rotated_at: datetime | None
    last_test_at: datetime | None
    last_test_status: str | None
    expiry_warning_days: int | None = None


class DocumentRowResponse(BaseModel):
    id: UUID
    file_name: str
    size_bytes: int
    content_type: str
    status: str
    index_progress: int
    index_stage: str
    processed_units: int
    total_units: int | None
    indexed_chunk_count: int
    index_started_at: datetime | None
    index_finished_at: datetime | None
    index_progress_updated_at: datetime | None
    queue_ahead: int | None = None
    failure_reason: str | None
    visibility_mode: str
    sensitivity_flag: bool
    acl_reviewed: bool
    created_at: datetime
    chunks_stored: int = 0
    chunks_with_embedding: int = 0
    embedding_dimensions: int | None = None
    search_ready: bool = False
    embedding_model: str | None = None
    embedding_mismatch: bool = False
    leftover_project_ids: list[str] = Field(default_factory=list)
    leftover_visibility_modes: list[str] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentRowResponse]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]
    worker_reachable: bool = True
    queue_wait_warning: bool = False


class MemberInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="EDITOR")

    @field_validator("email", "full_name", mode="before")
    @classmethod
    def strip_fields(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()


class MemberRow(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    membership_status: str = "active"


class UsageSummaryResponse(BaseModel):
    queries_last_30_days: int
    active_users: int
    storage_bytes: int
    indexed_documents: int


class AuditRowResponse(BaseModel):
    id: UUID
    created_at: datetime
    action: str
    resource_type: str
    actor_email: str | None


class AuditListResponse(BaseModel):
    items: list[AuditRowResponse]
    total: int
    page: int
    page_size: int


class AuditCleanupResponse(BaseModel):
    deleted_count: int
    scope: str

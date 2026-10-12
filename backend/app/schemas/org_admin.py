from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
    failure_reason: str | None
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentRowResponse]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class MemberInviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="EDITOR")


class MemberRow(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


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

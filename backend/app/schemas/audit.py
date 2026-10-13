from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    action: str
    resource_type: str
    resource_id: str | None
    user_id: UUID | None
    event_metadata: dict = Field(default_factory=dict)
    created_at: datetime


class ActivityEventResponse(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: str | None = None
    created_at: datetime
    actor_user_id: UUID | None = None
    actor_name: str
    actor_email: str | None = None
    actor_deleted_id: str | None = None
    target_label: str | None = None
    summary: str
    category: str
    secondary: str
    action_group: str
    is_security: bool = False
    is_failure: bool = False
    result: str = "Success"
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    changes: dict | None = None
    metadata_safe: dict = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    items: list[ActivityEventResponse]
    total: int
    offset: int
    limit: int
    next_offset: int | None = None


class ActivityActorOption(BaseModel):
    user_id: UUID
    name: str
    email: str


class ActivityActorsResponse(BaseModel):
    items: list[ActivityActorOption]

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    action: str
    resource_type: str
    resource_id: str | None
    user_id: UUID | None
    event_metadata: dict = {}
    created_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    offset: int
    limit: int

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    description: str | None = None


class ProjectSummaryResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    questionnaire_count: int
    source_count: int
    evidence_item_count: int
    pending_review_count: int
    potentially_stale_count: int
    updated_at: datetime

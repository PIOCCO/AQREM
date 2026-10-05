from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import EvidenceScope, SourceType


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str


class ProjectInitialSourceCreate(BaseModel):
    """Optional source to attach when creating a project (same fields as SourceCreate)."""

    name: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    scope: EvidenceScope = EvidenceScope.PROJECT
    config: dict = Field(default_factory=dict)
    repository_full_name: str | None = Field(
        default=None,
        description="GitHub owner/repo when source_type is github",
    )
    branch: str = "main"
    access_token: str | None = Field(default=None, description="Dev-only GitHub PAT")


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    initial_source: ProjectInitialSourceCreate | None = None


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

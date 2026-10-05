from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import EvidenceScope, SourceType


class SourceCreate(BaseModel):
    name: str
    source_type: SourceType
    project_id: UUID | None = None
    scope: EvidenceScope = EvidenceScope.PROJECT
    config: dict = Field(default_factory=dict)


class SourceResponse(BaseModel):
    id: UUID
    organization_id: UUID
    project_id: UUID | None
    name: str
    source_type: str
    scope: str
    status: str
    config: dict
    created_at: datetime


class GitHubRepoConnectRequest(BaseModel):
    source_id: UUID
    repository_full_name: str = Field(description="owner/repo")
    branch: str = "main"
    access_token: str | None = Field(
        default=None,
        description="Dev-only PAT; production uses GitHub App installation token",
    )


class SyncJobResponse(BaseModel):
    id: UUID
    source_id: UUID
    status: str
    stats: dict
    error_message: str | None
    created_at: datetime

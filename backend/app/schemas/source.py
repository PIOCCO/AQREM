from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from app.models.enums import EvidenceScope, SourceType

_SENSITIVE_CONFIG_KEYS = frozenset({"github_token", "access_token", "api_key", "password", "secret"})


def redact_source_config(config: dict | None) -> dict:
    if not config:
        return {}
    safe = dict(config)
    for key in list(safe.keys()):
        if key.lower() in _SENSITIVE_CONFIG_KEYS or key.lower().endswith("_token"):
            safe[key] = "[redacted]"
    return safe


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

    @field_serializer("config")
    def serialize_config(self, config: dict) -> dict:
        return redact_source_config(config)


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

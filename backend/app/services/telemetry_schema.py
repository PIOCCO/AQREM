"""Strict typed telemetry payloads (extra fields rejected)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SeatUsageTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seats_used: int = Field(ge=0)
    seats_limit: int = Field(ge=0)


class CredentialExpiryTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expires_at_iso: str | None = None
    status: str


class DocumentIndexingTelemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    indexed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    indexing_count: int = Field(ge=0)


TELEMETRY_FIELD_CATALOG: list[dict[str, str]] = [
    {"field": "seats_used", "description": "Number of licensed seats in use (members + pending invites)."},
    {"field": "seats_limit", "description": "Licensed seat limit for the organization."},
    {"field": "expires_at_iso", "description": "Model token expiry date (ISO date only, no secret)."},
    {"field": "status", "description": "Credential or indexing status code."},
    {"field": "indexed_count", "description": "Count of successfully indexed documents."},
    {"field": "failed_count", "description": "Count of failed document indexing jobs."},
    {"field": "indexing_count", "description": "Documents currently indexing."},
    {"field": "setup_step_flags", "description": "Boolean flags for setup checklist completion (no content)."},
    {"field": "environment_version", "description": "Deployed environment version string."},
    {"field": "error_code", "description": "Machine-readable error code without PII."},
]


def build_telemetry_payload(event_type: str, payload: dict) -> dict:
    from app.services.telemetry import validate_control_plane_payload

    validated = validate_control_plane_payload(event_type, payload)
    if event_type == "license.seat_usage_changed":
        return SeatUsageTelemetry(**validated).model_dump()
    if event_type == "credential.expiry_metadata_updated":
        return CredentialExpiryTelemetry(**validated).model_dump()
    if event_type in {"document.indexing_job_completed", "document.indexing_job_failed"}:
        return DocumentIndexingTelemetry(**validated).model_dump()
    return validated

"""Content-free control-plane telemetry allowlist."""

from __future__ import annotations

FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "document_text",
        "content",
        "embedding",
        "embeddings",
        "question",
        "answer",
        "prompt",
        "api_key",
        "secret",
        "token",
        "password",
        "file_name",
        "file_path",
    }
)

ALLOWED_EVENT_TYPES = frozenset(
    {
        "environment.health_changed",
        "source.configuration_status_changed",
        "document.indexing_job_completed",
        "document.indexing_job_failed",
        "license.seat_usage_changed",
        "credential.expiry_metadata_updated",
        "environment.version_changed",
    }
)


class TelemetryRejected(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def validate_control_plane_payload(event_type: str, payload: dict) -> dict:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise TelemetryRejected(f"Event type not allowlisted: {event_type}")
    sanitized: dict = {}
    for key, value in payload.items():
        lower = key.lower()
        if lower in FORBIDDEN_PAYLOAD_KEYS:
            raise TelemetryRejected(f"Disallowed payload field: {key}")
        if isinstance(value, str) and len(value) > 500:
            raise TelemetryRejected(f"Payload field too large: {key}")
        sanitized[key] = value
    return sanitized

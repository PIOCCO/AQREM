import pytest

from app.services.telemetry import TelemetryRejected, validate_control_plane_payload


def test_allows_safe_event():
    payload = validate_control_plane_payload(
        "license.seat_usage_changed",
        {"seats_used": 3, "seats_limit": 10},
    )
    assert payload["seats_used"] == 3


def test_rejects_disallowed_field():
    with pytest.raises(TelemetryRejected, match="document_text|content"):
        validate_control_plane_payload(
            "document.indexing_job_completed",
            {"document_text": "secret policy"},
        )


def test_rejects_unknown_event_type():
    with pytest.raises(TelemetryRejected):
        validate_control_plane_payload("employee.question_logged", {"count": 1})

"""Persist allow-listed telemetry from L2 into the L1 control-plane store."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.environment import ClientEnvironment, ControlPlaneEvent
from app.services.telemetry import TelemetryRejected, validate_control_plane_payload
from app.services.telemetry_schema import build_telemetry_payload


def ingest_org_telemetry(
    db: Session,
    *,
    organization_id: UUID,
    event_type: str,
    payload: dict,
) -> ControlPlaneEvent:
    """Validate payload (schema + allow-list) and append a control-plane event."""
    safe_inner = build_telemetry_payload(event_type, payload)
    env = (
        db.query(ClientEnvironment)
        .filter(ClientEnvironment.organization_id == organization_id)
        .order_by(ClientEnvironment.created_at.desc())
        .first()
    )
    event = ControlPlaneEvent(
        organization_id=organization_id,
        environment_id=env.environment_id if env else None,
        event_type=event_type,
        payload=safe_inner,
    )
    db.add(event)
    return event


def ingest_org_telemetry_safe(
    db: Session,
    *,
    organization_id: UUID,
    event_type: str,
    payload: dict,
) -> None:
    try:
        ingest_org_telemetry(db, organization_id=organization_id, event_type=event_type, payload=payload)
    except TelemetryRejected:
        raise
    except Exception:
        # Telemetry must not break L2 operations; callers log separately in tests.
        return

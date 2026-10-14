"""Dedupe admin console enter audit noise."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.models.audit import AuditEvent

DEDUPE_WINDOW = timedelta(minutes=15)


def record_admin_console_entered(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    request_id: str | None = None,
) -> bool:
    """Return True if a new audit row was written."""
    since = datetime.now(UTC) - DEDUPE_WINDOW
    recent = (
        db.query(AuditEvent.id)
        .filter(
            AuditEvent.organization_id == organization_id,
            AuditEvent.user_id == user_id,
            AuditEvent.action == "admin_console_entered",
            AuditEvent.created_at >= since,
        )
        .first()
    )
    if recent is not None:
        return False
    record_audit(
        db,
        organization_id=organization_id,
        user_id=user_id,
        action="admin_console_entered",
        resource_type="admin_console",
        resource_id=str(organization_id),
        metadata={"request_id": request_id} if request_id else {},
    )
    return True

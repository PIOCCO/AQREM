from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_audit(
    db: Session,
    *,
    organization_id: UUID,
    user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event

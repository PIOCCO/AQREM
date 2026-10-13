from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def _filters(
    *,
    organization_id: UUID,
    search: str | None,
    actions: list[str] | None,
    actor_user_ids: list[UUID] | None,
    date_from: datetime | None,
    date_to: datetime | None,
):
    clauses = [AuditEvent.organization_id == organization_id]
    if actions:
        clauses.append(AuditEvent.action.in_(actions))
    if actor_user_ids:
        clauses.append(AuditEvent.user_id.in_(actor_user_ids))
    if date_from:
        clauses.append(AuditEvent.created_at >= date_from)
    if date_to:
        clauses.append(AuditEvent.created_at <= date_to)
    if search:
        term = f"%{search.strip().lower()}%"
        clauses.append(
            or_(
                AuditEvent.action.ilike(term),
                AuditEvent.resource_type.ilike(term),
                cast(AuditEvent.event_metadata, String).ilike(term),
            )
        )
    return clauses


def audit_events_query(
    db: Session,
    *,
    organization_id: UUID,
    search: str | None = None,
    actions: list[str] | None = None,
    actor_user_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = "newest",
):
    clauses = _filters(
        organization_id=organization_id,
        search=search,
        actions=actions,
        actor_user_ids=actor_user_ids,
        date_from=date_from,
        date_to=date_to,
    )
    q = select(AuditEvent).where(*clauses)
    if sort == "oldest":
        q = q.order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
    else:
        q = q.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    return q


def audit_events_count(
    db: Session,
    *,
    organization_id: UUID,
    search: str | None = None,
    actions: list[str] | None = None,
    actor_user_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> int:
    from sqlalchemy import func

    clauses = _filters(
        organization_id=organization_id,
        search=search,
        actions=actions,
        actor_user_ids=actor_user_ids,
        date_from=date_from,
        date_to=date_to,
    )
    return db.scalar(select(func.count()).select_from(AuditEvent).where(*clauses)) or 0

import csv
import io
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.organization import User
from app.schemas.audit import ActivityActorOption, ActivityActorsResponse, ActivityEventResponse, AuditListResponse
from app.services.audit.presentation import enrich_event, load_users_for_events
from app.services.audit.query import audit_events_count, audit_events_query

router = APIRouter()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    action: str | None = Query(default=None),
    actions: list[str] | None = Query(default=None),
    actor_user_id: list[UUID] | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditListResponse:
    merged_actions = list(actions or [])
    if action and action not in merged_actions:
        merged_actions.append(action)

    base = audit_events_query(
        db,
        organization_id=tenant.organization_id,
        search=search,
        actions=merged_actions or None,
        actor_user_ids=actor_user_id,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        sort=sort,
    )
    total = audit_events_count(
        db,
        organization_id=tenant.organization_id,
        search=search,
        actions=merged_actions or None,
        actor_user_ids=actor_user_id,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
    )
    rows = db.scalars(base.offset(offset).limit(limit)).all()
    users = load_users_for_events(db, rows)
    items = [ActivityEventResponse(**enrich_event(row, users)) for row in rows]
    next_offset = offset + limit if offset + limit < total else None
    return AuditListResponse(items=items, total=total, offset=offset, limit=limit, next_offset=next_offset)


@router.get("/actors", response_model=ActivityActorsResponse)
def list_activity_actors(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ActivityActorsResponse:
    subq = (
        select(AuditEvent.user_id)
        .where(AuditEvent.organization_id == tenant.organization_id, AuditEvent.user_id.is_not(None))
        .distinct()
    )
    user_ids = list(db.scalars(subq).all())
    if not user_ids:
        return ActivityActorsResponse(items=[])
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    items = [
        ActivityActorOption(
            user_id=u.id,
            name=(u.full_name or "").strip() or u.email.split("@")[0],
            email=u.email,
        )
        for u in sorted(users, key=lambda x: x.email.lower())
    ]
    return ActivityActorsResponse(items=items)


@router.get("/export")
def export_audit_events(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    search: str | None = Query(default=None, max_length=200),
    actions: list[str] | None = Query(default=None),
    actor_user_id: list[UUID] | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort: str = Query(default="newest", pattern="^(newest|oldest)$"),
    limit: int = Query(default=5000, ge=1, le=10000),
) -> Response:
    base = audit_events_query(
        db,
        organization_id=tenant.organization_id,
        search=search,
        actions=actions,
        actor_user_ids=actor_user_id,
        date_from=_parse_dt(date_from),
        date_to=_parse_dt(date_to),
        sort=sort,
    )
    rows = db.scalars(base.limit(limit)).all()
    users = load_users_for_events(db, rows)
    enriched = [enrich_event(row, users) for row in rows]

    if format == "json":
        body = json.dumps(enriched, default=str, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="activity-export.json"'},
        )

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["id", "created_at", "summary", "action", "category", "actor_name", "actor_email", "result"],
    )
    writer.writeheader()
    for row in enriched:
        writer.writerow(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "summary": row["summary"],
                "action": row["action"],
                "category": row["category"],
                "actor_name": row["actor_name"],
                "actor_email": row["actor_email"] or "",
                "result": row["result"],
            }
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="activity-export.csv"'},
    )

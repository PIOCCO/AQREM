from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.schemas.audit import AuditEventResponse, AuditListResponse

router = APIRouter()


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    action: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditListResponse:
    query = db.query(AuditEvent).filter(AuditEvent.organization_id == tenant.organization_id)
    if action:
        query = query.filter(AuditEvent.action == action)
    total = query.count()
    rows = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()
    return AuditListResponse(
        items=[AuditEventResponse.model_validate(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )

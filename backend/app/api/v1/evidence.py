from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.evidence import EvidenceItem
from app.schemas.evidence import EvidenceItemResponse

router = APIRouter()


@router.get("", response_model=list[EvidenceItemResponse])
def list_evidence(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
    source_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EvidenceItem]:
    query = db.query(EvidenceItem).filter(EvidenceItem.organization_id == tenant.organization_id)
    if project_id:
        query = query.filter(
            (EvidenceItem.project_id == project_id) | (EvidenceItem.project_id.is_(None))
        )
    if source_id:
        query = query.filter(EvidenceItem.source_id == source_id)
    if search:
        query = query.filter(
            EvidenceItem.file_path.ilike(f"%{search}%")
            | EvidenceItem.content.ilike(f"%{search}%")
            | EvidenceItem.file_name.ilike(f"%{search}%")
        )
    return query.order_by(EvidenceItem.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/{evidence_id}", response_model=EvidenceItemResponse)
def get_evidence(
    evidence_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> EvidenceItem:
    item = db.get(EvidenceItem, evidence_id)
    if item is None or item.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return item

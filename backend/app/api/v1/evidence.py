from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.evidence import EvidenceItem
from app.schemas.evidence import (
    EvidenceItemResponse,
    EvidenceItemSummaryResponse,
    EvidenceListResponse,
)

router = APIRouter()

_LIST_CONTENT_MAX = 2000
_DETAIL_CONTENT_MAX = 512_000


def _summary(row: EvidenceItem) -> EvidenceItemSummaryResponse:
    raw = row.content or ""
    truncated = len(raw) > _LIST_CONTENT_MAX
    preview = raw if not truncated else raw[:_LIST_CONTENT_MAX] + "…"
    return EvidenceItemSummaryResponse(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        source_id=row.source_id,
        source_type=row.source_type,
        scope=row.scope,
        file_name=row.file_name,
        file_path=row.file_path,
        content=preview,
        content_truncated=truncated,
        content_type=row.content_type,
        language=row.language,
        repository=row.repository,
        branch=row.branch,
        commit_hash=row.commit_hash,
        line_start=row.line_start,
        line_end=row.line_end,
        symbol_name=row.symbol_name,
        symbol_kind=row.symbol_kind,
        evidence_strength=row.evidence_strength,
        chunk_index=row.chunk_index,
        created_at=row.created_at,
    )


@router.get("", response_model=EvidenceListResponse)
def list_evidence(
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    project_id: UUID | None = Query(default=None),
    source_id: UUID | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> EvidenceListResponse:
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
    total = query.count()
    rows = query.order_by(EvidenceItem.created_at.desc()).offset(offset).limit(limit).all()
    return EvidenceListResponse(
        items=[_summary(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


def _detail(row: EvidenceItem) -> EvidenceItemResponse:
    raw = row.content or ""
    truncated = len(raw) > _DETAIL_CONTENT_MAX
    preview = raw if not truncated else raw[:_DETAIL_CONTENT_MAX] + "…"
    return EvidenceItemResponse(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        source_id=row.source_id,
        source_type=row.source_type,
        scope=row.scope,
        file_name=row.file_name,
        file_path=row.file_path,
        content=preview,
        content_truncated=truncated,
        content_type=row.content_type,
        language=row.language,
        repository=row.repository,
        branch=row.branch,
        commit_hash=row.commit_hash,
        line_start=row.line_start,
        line_end=row.line_end,
        symbol_name=row.symbol_name,
        symbol_kind=row.symbol_kind,
        evidence_strength=row.evidence_strength,
        chunk_index=row.chunk_index,
        created_at=row.created_at,
    )


@router.get("/{evidence_id}", response_model=EvidenceItemResponse)
def get_evidence(
    evidence_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> EvidenceItemResponse:
    item = db.get(EvidenceItem, evidence_id)
    if item is None or item.organization_id != tenant.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return _detail(item)

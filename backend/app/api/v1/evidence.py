from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
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


def _list_query(db: Session, tenant: TenantContext):
    content_len = func.length(EvidenceItem.content)
    content_preview = func.left(EvidenceItem.content, _LIST_CONTENT_MAX)
    truncated = content_len > _LIST_CONTENT_MAX
    return (
        db.query(
            EvidenceItem.id,
            EvidenceItem.organization_id,
            EvidenceItem.project_id,
            EvidenceItem.source_id,
            EvidenceItem.source_type,
            EvidenceItem.scope,
            EvidenceItem.file_name,
            EvidenceItem.file_path,
            content_preview.label("content"),
            truncated.label("content_truncated"),
            EvidenceItem.content_type,
            EvidenceItem.language,
            EvidenceItem.repository,
            EvidenceItem.branch,
            EvidenceItem.commit_hash,
            EvidenceItem.line_start,
            EvidenceItem.line_end,
            EvidenceItem.symbol_name,
            EvidenceItem.symbol_kind,
            EvidenceItem.evidence_strength,
            EvidenceItem.chunk_index,
            EvidenceItem.created_at,
        )
        .filter(EvidenceItem.organization_id == tenant.organization_id)
    )


def _row_to_summary(row) -> EvidenceItemSummaryResponse:
    content = row.content or ""
    if row.content_truncated:
        content = f"{content}…"
    return EvidenceItemSummaryResponse(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        source_id=row.source_id,
        source_type=row.source_type,
        scope=row.scope,
        file_name=row.file_name,
        file_path=row.file_path,
        content=content,
        content_truncated=bool(row.content_truncated),
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
    limit: int = Query(default=25, le=100),
    offset: int = Query(default=0, ge=0),
) -> EvidenceListResponse:
    query = _list_query(db, tenant)
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
        items=[_row_to_summary(row) for row in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{evidence_id}", response_model=EvidenceItemResponse)
def get_evidence(
    evidence_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> EvidenceItemResponse:
    content_len = func.length(EvidenceItem.content)
    content_preview = func.left(EvidenceItem.content, _DETAIL_CONTENT_MAX)
    truncated = content_len > _DETAIL_CONTENT_MAX
    row = (
        db.query(
            EvidenceItem.id,
            EvidenceItem.organization_id,
            EvidenceItem.project_id,
            EvidenceItem.source_id,
            EvidenceItem.source_type,
            EvidenceItem.scope,
            EvidenceItem.file_name,
            EvidenceItem.file_path,
            content_preview.label("content"),
            truncated.label("content_truncated"),
            EvidenceItem.content_type,
            EvidenceItem.language,
            EvidenceItem.repository,
            EvidenceItem.branch,
            EvidenceItem.commit_hash,
            EvidenceItem.line_start,
            EvidenceItem.line_end,
            EvidenceItem.symbol_name,
            EvidenceItem.symbol_kind,
            EvidenceItem.evidence_strength,
            EvidenceItem.chunk_index,
            EvidenceItem.created_at,
        )
        .filter(
            EvidenceItem.id == evidence_id,
            EvidenceItem.organization_id == tenant.organization_id,
        )
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    content = row.content or ""
    if row.content_truncated:
        content = f"{content}…"
    return EvidenceItemResponse(
        id=row.id,
        organization_id=row.organization_id,
        project_id=row.project_id,
        source_id=row.source_id,
        source_type=row.source_type,
        scope=row.scope,
        file_name=row.file_name,
        file_path=row.file_path,
        content=content,
        content_truncated=bool(row.content_truncated),
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

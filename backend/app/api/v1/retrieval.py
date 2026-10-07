from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.rate_limit import RETRIEVAL_PREVIEW_LIMIT, limiter
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.schemas.evidence import EvidenceItemSummaryResponse, EvidenceSearchRequest, RetrievalPreviewResponse
from app.services.llm.guardrails import sanitize_evidence_content
from app.services.retrieval.service import RetrievalService

router = APIRouter()


@router.post("/preview", response_model=RetrievalPreviewResponse)
@limiter.limit(RETRIEVAL_PREVIEW_LIMIT)
async def preview_retrieval(
    request: Request,
    payload: EvidenceSearchRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> RetrievalPreviewResponse:
    items = await RetrievalService(db).retrieve(
        organization_id=tenant.organization_id,
        query=payload.query,
        project_id=payload.project_id,
        source_id=payload.source_id,
        limit=payload.limit,
    )
    preview_items = [
        EvidenceItemSummaryResponse(
            id=i.id,
            organization_id=i.organization_id,
            project_id=i.project_id,
            source_id=i.source_id,
            source_type=i.source_type,
            scope=i.scope,
            file_name=i.file_name,
            file_path=i.file_path,
            content=sanitize_evidence_content(i.content),
            content_truncated=len(i.content or "") > 2000,
            content_type=i.content_type,
            language=i.language,
            repository=i.repository,
            branch=i.branch,
            commit_hash=i.commit_hash,
            line_start=i.line_start,
            line_end=i.line_end,
            symbol_name=i.symbol_name,
            symbol_kind=i.symbol_kind,
            evidence_strength=i.evidence_strength,
            chunk_index=i.chunk_index,
            created_at=i.created_at,
        )
        for i in items
    ]
    return RetrievalPreviewResponse(query=payload.query, items=preview_items)

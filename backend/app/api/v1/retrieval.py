from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.schemas.evidence import EvidenceItemResponse, EvidenceSearchRequest, RetrievalPreviewResponse
from app.services.retrieval.service import RetrievalService

router = APIRouter()


@router.post("/preview", response_model=RetrievalPreviewResponse)
async def preview_retrieval(
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
    return RetrievalPreviewResponse(
        query=payload.query,
        items=[EvidenceItemResponse.model_validate(i) for i in items],
    )

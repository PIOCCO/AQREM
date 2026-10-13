from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.rate_limit import RETRIEVAL_PREVIEW_LIMIT, limiter
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.schemas.chat import ChatAskRequest, ChatAskResponse
from app.services.chat.service import ChatAskService

router = APIRouter()


@router.post("/ask", response_model=ChatAskResponse)
@limiter.limit(RETRIEVAL_PREVIEW_LIMIT)
async def ask_chat(
    request: Request,
    payload: ChatAskRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ChatAskResponse:
    result = await ChatAskService(db).ask(
        organization_id=tenant.organization_id,
        query=payload.query,
        project_id=payload.project_id,
        user_id=tenant.user_id,
    )
    return ChatAskResponse(**result)

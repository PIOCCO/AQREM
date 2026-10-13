from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.rate_limit import RETRIEVAL_PREVIEW_LIMIT, limiter
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.schemas.chat import (
    ChatAskRequest,
    ChatAskResponse,
    ChatShareViewResponse,
    CreateChatShareRequest,
    CreateChatShareResponse,
)
from app.services.chat.service import ChatAskService
from app.services.chat.share_service import ChatShareService

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


@router.post("/shares", response_model=CreateChatShareResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_share(
    payload: CreateChatShareRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> CreateChatShareResponse:
    messages = [m.model_dump() for m in payload.messages]
    share = ChatShareService(db).create_or_update_share(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        client_conversation_id=payload.client_conversation_id,
        title=payload.title,
        messages=messages,
    )
    db.commit()
    return CreateChatShareResponse(share_token=share.share_token, share_path=f"/share/{share.share_token}")


@router.get("/shares/{token}", response_model=ChatShareViewResponse)
async def get_chat_share(
    token: str,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> ChatShareViewResponse:
    share = ChatShareService(db).get_share_for_tenant(token=token, organization_id=tenant.organization_id)
    return ChatShareViewResponse(
        title=share.title,
        messages=share.messages,
        shared_at=share.updated_at or share.created_at,
    )


@router.delete("/shares/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_chat_share(
    token: str,
    tenant: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> None:
    is_admin = tenant.role == Role.ORG_ADMIN
    ChatShareService(db).revoke_share(
        token=token,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        is_org_admin=is_admin,
    )
    db.commit()

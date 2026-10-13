from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.access_deps import get_user_access
from app.core.dependencies import get_tenant_context
from app.services.access_control.context import UserAccessContext
from app.core.rate_limit import RETRIEVAL_PREVIEW_LIMIT, limiter
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.tenant_store.deps import get_tenant_db
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
    access: UserAccessContext = Depends(get_user_access),
    db: Session = Depends(get_tenant_db),
) -> ChatAskResponse:
    result = await ChatAskService(db).ask(
        organization_id=tenant.organization_id,
        query=payload.query,
        project_id=payload.project_id,
        user_id=tenant.user_id,
        access=access,
    )
    return ChatAskResponse(**result)


@router.post("/shares", response_model=CreateChatShareResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_share(
    payload: CreateChatShareRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    control_db: Session = Depends(get_db),
    db: Session = Depends(get_tenant_db),
) -> CreateChatShareResponse:
    messages = [m.model_dump() for m in payload.messages]
    share = ChatShareService(db, control_db=control_db).create_or_update_share(
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        client_conversation_id=payload.client_conversation_id,
        title=payload.title,
        messages=messages,
    )
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="chat_share_created",
        resource_type="chat_share",
        resource_id=share.share_token[:16],
        metadata={"client_conversation_id": payload.client_conversation_id},
    )
    db.flush()
    control_db.flush()
    db.commit()
    if control_db is not db:
        control_db.commit()
    return CreateChatShareResponse(share_token=share.share_token, share_path=f"/share/{share.share_token}")


@router.get("/shares/{token}", response_model=ChatShareViewResponse)
async def get_chat_share(
    token: str,
    tenant: TenantContext = Depends(get_tenant_context),
    control_db: Session = Depends(get_db),
    db: Session = Depends(get_tenant_db),
) -> ChatShareViewResponse:
    share = ChatShareService(db, control_db=control_db).get_share_for_tenant(
        token=token, organization_id=tenant.organization_id
    )
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="chat_share_viewed",
        resource_type="chat_share",
        resource_id=token[:16],
        metadata={"authenticated": True},
    )
    db.commit()
    return ChatShareViewResponse(
        title=share.title,
        messages=share.messages,
        shared_at=share.updated_at or share.created_at,
    )


@router.delete("/shares/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_chat_share(
    token: str,
    tenant: TenantContext = Depends(get_tenant_context),
    control_db: Session = Depends(get_db),
    db: Session = Depends(get_tenant_db),
) -> None:
    is_admin = tenant.role == Role.ORG_ADMIN
    ChatShareService(db, control_db=control_db).revoke_share(
        token=token,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        is_org_admin=is_admin,
    )
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="chat_share_revoked",
        resource_type="chat_share",
        resource_id=token[:16],
        metadata={},
    )
    db.commit()
    if control_db is not db:
        control_db.commit()

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.rate_limit import PUBLIC_SHARE_LIMIT, limiter
from app.db.session import get_db
from app.models.chat_share_index import ChatShareTokenIndex
from app.schemas.chat import ChatShareViewResponse
from app.services.chat.share_service import ChatShareService
from app.tenant_store.resolver import MANAGED_COLOCATED, ensure_managed_config, open_tenant_session

router = APIRouter()


def _index_valid(index: ChatShareTokenIndex | None) -> ChatShareTokenIndex:
    if index is None or index.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")
    exp = index.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found or expired")
    return index


def _tenant_session_for_org(control_db: Session, organization_id) -> tuple[Session, bool]:
    cfg = ensure_managed_config(control_db, organization_id)
    if cfg.storage_mode == MANAGED_COLOCATED:
        return control_db, False
    return open_tenant_session(control_db, organization_id), True


@router.get("/shares/{token}", response_model=ChatShareViewResponse)
@limiter.limit(PUBLIC_SHARE_LIMIT)
def view_public_chat_share(token: str, request: Request, control_db: Session = Depends(get_db)) -> JSONResponse:
    index = _index_valid(control_db.get(ChatShareTokenIndex, token))
    tenant_db, close_tenant = _tenant_session_for_org(control_db, index.organization_id)
    try:
        share = ChatShareService(tenant_db, control_db=control_db).get_share_for_tenant(
            token=token,
            organization_id=index.organization_id,
        )
        record_audit(
            tenant_db,
            organization_id=index.organization_id,
            user_id=None,
            action="chat_share_viewed",
            resource_type="chat_share",
            resource_id=token[:16],
            metadata={"public": True},
        )
        tenant_db.commit()
        body = ChatShareViewResponse(
            title=share.title,
            messages=share.messages,
            shared_at=share.updated_at or share.created_at,
        )
        return JSONResponse(
            content=body.model_dump(mode="json"),
            headers={"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"},
        )
    finally:
        if close_tenant:
            tenant_db.close()

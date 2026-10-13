"""Public employee join endpoints (unauthenticated)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.jwt_audiences import AUD_EMPLOYEE
from app.core.rate_limit import AUTH_LOGIN_LIMIT, limiter
from app.core.roles import Role
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import TokenResponse
from app.schemas.invitations import (
    JoinCompleteRequest,
    JoinCompleteResponse,
    JoinPreviewRequest,
    JoinPreviewResponse,
    JoinStartRequest,
    JoinStartResponse,
    JoinVerifyRequest,
    JoinVerifyResponse,
)
from app.services.invitations.employee_join import (
    GENERIC_JOIN_ERROR,
    join_complete,
    join_preview,
    join_start,
    join_verify_email,
)

router = APIRouter()

_GENERIC = {"message": GENERIC_JOIN_ERROR}


@router.post("/preview", response_model=JoinPreviewResponse)
@limiter.limit("30/minute")
def preview_join(request: Request, payload: JoinPreviewRequest, db: Session = Depends(get_db)) -> JoinPreviewResponse:
    try:
        data = join_preview(db, payload.token)
    except ValueError:
        raise HTTPException(status_code=404, detail=_GENERIC) from None
    return JoinPreviewResponse(**data)


@router.post("/start", response_model=JoinStartResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def start_join(request: Request, payload: JoinStartRequest, db: Session = Depends(get_db)) -> JoinStartResponse:
    settings = get_settings()
    try:
        pending, dev_code = join_start(
            db,
            token=payload.token,
            email=payload.email,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        msg = str(exc)
        if "no available seats" in msg.lower():
            raise HTTPException(status_code=403, detail={"message": msg}) from exc
        raise HTTPException(status_code=400, detail=_GENERIC) from exc
    db.commit()
    dev_field = dev_code if settings.app_env != "production" else None
    return JoinStartResponse(
        pending_id=pending.id,
        verification_required=True,
        dev_verification_code=dev_field,
    )


@router.post("/verify-email", response_model=JoinVerifyResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def verify_join_email(
    request: Request, payload: JoinVerifyRequest, db: Session = Depends(get_db)
) -> JoinVerifyResponse:
    try:
        pending = join_verify_email(
            db,
            token=payload.token,
            pending_id=payload.pending_id,
            code=payload.code,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=_GENERIC) from None
    db.commit()
    next_step = "password"
    return JoinVerifyResponse(pending_id=pending.id, next_step=next_step)


@router.post("/complete", response_model=JoinCompleteResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def complete_join(
    request: Request, payload: JoinCompleteRequest, db: Session = Depends(get_db)
) -> JoinCompleteResponse:
    try:
        user, membership, status = join_complete(
            db,
            token=payload.token,
            pending_id=payload.pending_id,
            password=payload.password,
        )
    except ValueError as exc:
        msg = str(exc)
        if "no available seats" in msg.lower():
            raise HTTPException(status_code=403, detail={"message": msg}) from exc
        raise HTTPException(status_code=400, detail=_GENERIC) from exc
    db.commit()

    if status == "pending_approval":
        return JoinCompleteResponse(status=status, organization_id=membership.organization_id)

    token = create_access_token(
        str(user.id),
        {
            "organization_id": str(membership.organization_id),
            "role": membership.role,
            "auth_version": membership.auth_version,
        },
        audience=AUD_EMPLOYEE,
    )
    return JoinCompleteResponse(
        status="joined",
        organization_id=membership.organization_id,
        access_token=token,
    )

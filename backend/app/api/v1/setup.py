"""Dedicated-tier first-run setup (create the first organization admin)."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.deployment import dedicated_setup_required, ensure_dedicated_organization
from app.core.roles import Role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User

router = APIRouter()


class SetupStatus(BaseModel):
    deployment_mode: str
    setup_required: bool
    organization_name: str | None = None
    setup_token_configured: bool = False


class FirstAdminRequest(BaseModel):
    setup_token: str = Field(min_length=1, max_length=512)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    organization_name: str | None = Field(default=None, max_length=255)


class FirstAdminResponse(BaseModel):
    organization_id: str
    organization_name: str
    email: str


@router.get("/status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)) -> SetupStatus:
    settings = get_settings()
    if not settings.is_dedicated:
        return SetupStatus(deployment_mode="shared", setup_required=False)
    org = ensure_dedicated_organization(db, settings)
    db.commit()
    return SetupStatus(
        deployment_mode="dedicated",
        setup_required=dedicated_setup_required(db),
        organization_name=org.name if org else None,
        setup_token_configured=bool((settings.setup_token or "").strip()),
    )


@router.post("/first-admin", response_model=FirstAdminResponse, status_code=status.HTTP_201_CREATED)
def create_first_admin(payload: FirstAdminRequest, db: Session = Depends(get_db)) -> FirstAdminResponse:
    settings = get_settings()
    if not settings.is_dedicated:
        raise HTTPException(status_code=404, detail="Not found")
    expected = (settings.setup_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail={"code": "SETUP_TOKEN_MISSING",
                    "message": "SETUP_TOKEN is not configured on this environment; ask your operator."},
        )
    if not hmac.compare_digest(payload.setup_token.strip().encode(), expected.encode()):
        raise HTTPException(status_code=403, detail={"code": "SETUP_TOKEN_INVALID", "message": "Setup token is incorrect."})

    org = ensure_dedicated_organization(db, settings)
    # Serialize concurrent setup attempts on the organization row.
    org = db.query(Organization).filter(Organization.id == org.id).with_for_update().one()
    if not dedicated_setup_required(db):
        raise HTTPException(status_code=409, detail={"code": "SETUP_DONE", "message": "Setup is already complete. Sign in instead."})

    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None:
        user = User(email=email, full_name=payload.full_name.strip(), hashed_password=hash_password(payload.password),
                    is_active=True, must_change_password=False)
        db.add(user)
        db.flush()
    else:
        user.hashed_password = hash_password(payload.password)
        user.is_active = True
    if payload.organization_name and payload.organization_name.strip():
        org.name = payload.organization_name.strip()
    db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value))
    record_audit(db, organization_id=org.id, user_id=user.id, action="dedicated_first_admin_created",
                 resource_type="organization", resource_id=str(org.id), metadata={})
    db.commit()
    return FirstAdminResponse(organization_id=str(org.id), organization_name=org.name, email=email)

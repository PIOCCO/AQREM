"""Dedicated-tier first-run setup (create the first organization admin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.config import get_settings
from app.core.deployment import ensure_dedicated_organization
from app.core.roles import Role
from app.core.security import hash_password
from app.db.session import get_db
from app.services import setup_guard
from app.models.organization import Organization, OrganizationMembership, User

router = APIRouter()


class SetupStatus(BaseModel):
    deployment_mode: str
    setup_required: bool
    organization_name: str | None = None
    setup_token_configured: bool = False
    license_state: str | None = None
    license_message: str | None = None
    expires_at: str | None = None


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


from starlette.exceptions import HTTPException as StarletteHTTPException

# Starlette's base exception bypasses the app's HTTPException handler, so the response is
# byte-identical to an unknown route ({"detail": "Not Found"}).
NOT_FOUND = StarletteHTTPException(status_code=404, detail="Not Found")


def _gate(request: Request, db: Session):
    """Return (settings, client_ip, state) or raise 404/410. Applied identically to every setup route."""
    settings = get_settings()
    if not settings.is_dedicated:
        raise NOT_FOUND
    ip = setup_guard.client_ip(request.client.host if request.client else None,
                               request.headers.get("x-forwarded-for"), settings)
    if not setup_guard.ip_allowed(ip, settings):
        raise NOT_FOUND
    st = setup_guard.setup_state(db, settings)
    db.commit()  # persist a freshly issued bootstrap token row
    if st.state == setup_guard.CLOSED:
        raise NOT_FOUND
    if st.state == setup_guard.EXPIRED:
        raise HTTPException(status_code=410, detail={
            "code": "SETUP_TOKEN_EXPIRED",
            "message": "The setup token has expired or was already used. Ask your operator to run "
                       "'python -m app.setup reset --confirm' to issue a new one."})
    return settings, ip, st


def _locked(seconds: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={"code": "SETUP_LOCKED", "message": "Too many failed attempts. Try again later.",
                "retry_after_seconds": seconds},
        headers={"Retry-After": str(seconds)},
    )


@router.get("/status", response_model=SetupStatus)
def setup_status(request: Request, db: Session = Depends(get_db)) -> SetupStatus:
    settings, ip, st = _gate(request, db)
    org = ensure_dedicated_organization(db, settings)
    db.commit()
    locked = setup_guard.lockout_seconds(db, ip, settings)
    if locked:
        raise _locked(locked)
    from app.services.offline_license import load_license

    lic = load_license(settings)
    return SetupStatus(
        deployment_mode="dedicated",
        setup_required=st.state == setup_guard.OPEN,
        organization_name=org.name if org else None,
        setup_token_configured=st.state == setup_guard.OPEN,
        license_state=lic.state,
        license_message=lic.message,
        expires_at=st.expires_at.isoformat() if st.expires_at else None,
    )


@router.post("/first-admin", response_model=FirstAdminResponse, status_code=status.HTTP_201_CREATED)
def create_first_admin(payload: FirstAdminRequest, request: Request, db: Session = Depends(get_db)) -> FirstAdminResponse:
    settings, ip, st = _gate(request, db)
    if st.state == setup_guard.UNCONFIGURED:
        raise HTTPException(
            status_code=503,
            detail={"code": "SETUP_TOKEN_MISSING",
                    "message": "SETUP_TOKEN is not configured on this environment; ask your operator."},
        )
    locked = setup_guard.lockout_seconds(db, ip, settings)
    if locked:
        raise _locked(locked)
    # Lock the token row: concurrent attempts serialize here, and a consumed token stays consumed.
    from app.models.setup_token import SetupToken

    row = db.query(SetupToken).filter(SetupToken.id == st.token.id).with_for_update().one()
    if not setup_guard.verify_token(row, payload.setup_token) or row.consumed_at is not None \
            or row.revoked_at is not None:
        setup_guard.record_attempt(db, ip, success=False)
        db.commit()
        raise HTTPException(status_code=403, detail={"code": "SETUP_TOKEN_INVALID", "message": "Setup token is incorrect."})

    org = ensure_dedicated_organization(db, settings)
    org = db.query(Organization).filter(Organization.id == org.id).with_for_update().one()

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
    existing = db.query(OrganizationMembership).filter_by(organization_id=org.id, user_id=user.id).one_or_none()
    if existing is None:
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.ORG_ADMIN.value))
    else:
        existing.role = Role.ORG_ADMIN.value
    from datetime import UTC, datetime

    row.consumed_at = datetime.now(UTC)
    setup_guard.record_attempt(db, ip, success=True)
    record_audit(db, organization_id=org.id, user_id=user.id, action="dedicated_first_admin_created",
                 resource_type="organization", resource_id=str(org.id), metadata={"token_source": row.source})
    db.commit()
    return FirstAdminResponse(organization_id=str(org.id), organization_name=org.name, email=email)

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_tenant_context
from app.core.roles import Role
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    org = Organization(name=payload.organization_name, slug=_slugify(payload.organization_name))
    db.add_all([user, org])
    db.flush()
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=Role.ORG_ADMIN.value,
    )
    db.add(membership)
    db.commit()

    token = create_access_token(
        str(user.id),
        {"organization_id": str(org.id), "role": Role.ORG_ADMIN.value},
    )
    return TokenResponse(access_token=token, organization_id=org.id, role=Role.ORG_ADMIN)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    membership_query = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id)
    if payload.organization_id:
        membership_query = membership_query.filter(
            OrganizationMembership.organization_id == payload.organization_id
        )
    membership = membership_query.first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")

    token = create_access_token(
        str(user.id),
        {"organization_id": str(membership.organization_id), "role": membership.role},
    )
    return TokenResponse(access_token=token, organization_id=membership.organization_id, role=Role(membership.role))


@router.get("/me", response_model=UserResponse)
def me(tenant: TenantContext = Depends(get_tenant_context)) -> UserResponse:
    return UserResponse(
        id=tenant.user_id,
        email=tenant.email,
        full_name=tenant.email.split("@")[0],
        organization_id=tenant.organization_id,
        role=tenant.role,
    )

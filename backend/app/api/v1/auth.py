from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_authenticated_user, get_tenant_context
from app.core.rate_limit import AUTH_LOGIN_LIMIT, limiter
from app.core.roles import Role
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User
from app.schemas.admin import AcceptInvitationRequest, ChangePasswordRequest
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.licensing import org_allows_sign_in
from app.services.platform_provisioning import accept_invitation

router = APIRouter()


@router.post("/register")
@limiter.limit(AUTH_LOGIN_LIMIT)
def register_removed(request: Request) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Contact your administrator for access.",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.is_active or not user.hashed_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Platform administrators may sign in without selecting an organization (admin console).
    if user.is_platform_admin and payload.organization_id is None:
        token = create_access_token(str(user.id), {"role": "PLATFORM_ADMIN", "aud": "aqrem-master"})
        return TokenResponse(
            access_token=token,
            organization_id=None,
            role=None,
            must_change_password=user.must_change_password,
            is_platform_admin=True,
        )

    membership_query = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.is_active.is_(True),
    )
    if payload.organization_id:
        membership_query = membership_query.filter(
            OrganizationMembership.organization_id == payload.organization_id
        )
    membership = membership_query.order_by(OrganizationMembership.id.asc()).first()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership")

    org = db.get(Organization, membership.organization_id)
    if org is None or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not available")

    allowed, reason = org_allows_sign_in(org)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    member_role = Role(membership.role)
    audience = "aqrem-org-admin" if member_role == Role.ORG_ADMIN else "aqrem-employee"
    token = create_access_token(
        str(user.id),
        {"organization_id": str(membership.organization_id), "role": membership.role, "aud": audience},
    )
    return TokenResponse(
        access_token=token,
        organization_id=membership.organization_id,
        role=member_role,
        must_change_password=user.must_change_password,
        is_platform_admin=user.is_platform_admin,
    )


@router.post("/accept-invitation", response_model=TokenResponse)
@limiter.limit(AUTH_LOGIN_LIMIT)
def accept_invite(
    request: Request,
    payload: AcceptInvitationRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user, membership = accept_invitation(
            db,
            token=payload.token.strip(),
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()

    org = db.get(Organization, membership.organization_id)
    if org is None:
        raise HTTPException(status_code=400, detail="Organization missing")
    allowed, reason = org_allows_sign_in(org)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    token = create_access_token(
        str(user.id),
        {"organization_id": str(membership.organization_id), "role": membership.role},
    )
    return TokenResponse(
        access_token=token,
        organization_id=membership.organization_id,
        role=Role(membership.role),
        must_change_password=False,
        is_platform_admin=user.is_platform_admin,
    )


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
) -> None:
    if not user.hashed_password or not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()


@router.get("/me", response_model=UserResponse)
def me(
    user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> UserResponse:
    organization_id: UUID | None = None
    role: Role | None = None

    if x_organization_id:
        organization_id = UUID(x_organization_id)
        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.organization_id == organization_id,
            )
            .first()
        )
        if membership and membership.is_active:
            role = Role(membership.role)
        elif membership and not membership.is_active:
            organization_id = None
    else:
        membership = (
            db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.is_active.is_(True))
            .order_by(OrganizationMembership.id.asc())
            .first()
        )
        if membership:
            organization_id = membership.organization_id
            role = Role(membership.role)

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=organization_id,
        role=role,
        is_platform_admin=user.is_platform_admin,
        must_change_password=user.must_change_password,
    )


@router.get("/me/tenant", response_model=UserResponse)
def me_tenant(tenant: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)) -> UserResponse:
    user = db.get(User, tenant.user_id)
    assert user is not None
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=tenant.organization_id,
        role=tenant.role,
        is_platform_admin=user.is_platform_admin,
        must_change_password=user.must_change_password,
    )

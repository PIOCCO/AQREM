from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.roles import Role, role_at_least
from app.core.security import decode_access_token
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMembership, User
from app.services.licensing import org_allows_sign_in

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = UUID(payload["sub"])
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_platform_admin(user: User = Depends(get_authenticated_user)) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator required")
    return user


def get_tenant_context(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
) -> TenantContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = UUID(payload["sub"])
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must change your password before using the application",
        )

    org_id_str = x_organization_id or payload.get("organization_id")
    if not org_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header or token organization_id required",
        )
    organization_id = UUID(org_id_str)

    org = db.get(Organization, organization_id)
    if org is None or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not available")

    allowed, reason = org_allows_sign_in(org)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )
    if membership is None or not membership.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of organization")

    return TenantContext(
        user_id=user_id,
        organization_id=organization_id,
        role=Role(membership.role),
        email=user.email,
    )


def require_org_admin(tenant: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    if not role_at_least(tenant.role, Role.ORG_ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization administrator required")
    return tenant


def require_role(required: Role):
    def _checker(tenant: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not role_at_least(tenant.role, required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return tenant

    return _checker

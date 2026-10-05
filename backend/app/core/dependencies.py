from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.roles import Role, role_at_least
from app.core.security import decode_access_token
from app.core.tenant import TenantContext
from app.db.session import get_db
from app.models.organization import OrganizationMembership, User

bearer_scheme = HTTPBearer(auto_error=False)


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
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    org_id_str = x_organization_id or payload.get("organization_id")
    if not org_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header or token organization_id required",
        )
    organization_id = UUID(org_id_str)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of organization")

    return TenantContext(
        user_id=user_id,
        organization_id=organization_id,
        role=Role(membership.role),
        email=user.email,
    )


def require_role(required: Role):
    def _checker(tenant: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not role_at_least(tenant.role, required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return tenant

    return _checker

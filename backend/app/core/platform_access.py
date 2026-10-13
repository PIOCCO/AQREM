"""Resolve platform staff role and enforce platform session invariants."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.permissions_catalog import has_platform_permission
from app.core.platform_roles import PlatformRole
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.organization import User

bearer_scheme = HTTPBearer(auto_error=False)


def resolve_platform_role(user: User) -> PlatformRole | None:
    raw = getattr(user, "platform_role", None)
    if raw:
        try:
            return PlatformRole(str(raw))
        except ValueError:
            return None
    if user.is_platform_admin:
        return PlatformRole.SUPER_ADMIN
    return None


def is_platform_staff(user: User) -> bool:
    return resolve_platform_role(user) is not None


def get_platform_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant session cannot access the platform console",
        )
    aud = payload.get("aud")
    if aud is not None and aud != "aqrem-master":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform console requires a master audience token",
        )

    from uuid import UUID

    user_id = UUID(payload["sub"])
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    role = resolve_platform_role(user)
    if role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform staff role required")

    token_ver = payload.get("platform_auth_version")
    user_ver = int(getattr(user, "platform_auth_version", 1) or 1)
    if token_ver is not None and int(token_ver) != user_ver:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")

    return user


def require_platform_permission(permission: str):
    def _dep(user: User = Depends(get_platform_user)) -> User:
        role = resolve_platform_role(user)
        if not has_platform_permission(role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _dep


def bump_platform_auth_version(db: Session, user: User) -> None:
    user.platform_auth_version = int(getattr(user, "platform_auth_version", 1) or 1) + 1

from app.core.jwt_audiences import AUD_EMPLOYEE, AUD_ORG_ADMIN, AUD_PLATFORM
from app.core.roles import Role
from app.core.security import create_access_token


def employee_token(user_id: str, org_id: str, *, role: str = Role.EDITOR.value, auth_version: int = 1) -> str:
    return create_access_token(
        user_id,
        {"organization_id": org_id, "role": role, "auth_version": auth_version},
        audience=AUD_EMPLOYEE,
    )


def org_admin_token(user_id: str, org_id: str, *, auth_version: int = 1) -> str:
    return create_access_token(
        user_id,
        {"organization_id": org_id, "role": Role.ORG_ADMIN.value, "auth_version": auth_version},
        audience=AUD_ORG_ADMIN,
    )


def platform_token(user_id: str, *, platform_auth_version: int = 1) -> str:
    return create_access_token(
        user_id,
        {"platform_role": "SUPER_ADMIN", "platform_auth_version": platform_auth_version},
        audience=AUD_PLATFORM,
    )

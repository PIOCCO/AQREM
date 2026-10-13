"""Server-computed permission strings for the authenticated tenant member."""

from app.core.roles import Role, role_at_least

ADMIN_CONSOLE_ACCESS = "admin_console:access"


def permissions_for_role(role: Role | None) -> list[str]:
    if role is not None and role_at_least(role, Role.ORG_ADMIN):
        return [ADMIN_CONSOLE_ACCESS]
    return []

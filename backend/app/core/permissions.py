"""Server-computed permission strings for tenant members (from permissions.yaml)."""

from app.core.permissions_catalog import organization_permissions_for_role
from app.core.roles import Role

ADMIN_CONSOLE_ACCESS = "admin_console:access"


def permissions_for_role(role: Role | None) -> list[str]:
    return organization_permissions_for_role(role)

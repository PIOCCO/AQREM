"""Authorization policy checks (Cerbos-compatible shape; default deny)."""

from __future__ import annotations

from app.core.roles import Role, role_at_least
from app.core.tenant import TenantContext


class PolicyDenied(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def assert_org_admin_action(
    tenant: TenantContext,
    *,
    action: str,
    resource_type: str,
    resource_org_id,
) -> None:
    if tenant.organization_id != resource_org_id:
        raise PolicyDenied("TENANT_MISMATCH", "Resource is not in your organization")
    if not role_at_least(tenant.role, Role.ORG_ADMIN):
        raise PolicyDenied("FORBIDDEN", "Organization administrator required")
    allowed = {
        ("read", "setup"),
        ("read", "document"),
        ("write", "document"),
        ("delete", "document"),
        ("read", "credential"),
        ("write", "credential"),
        ("read", "member"),
        ("write", "member"),
        ("read", "audit"),
        ("delete", "audit"),
        ("read", "usage"),
        ("read", "telemetry_schema"),
    }
    if (action, resource_type) not in allowed:
        raise PolicyDenied("FORBIDDEN", f"Action {action} on {resource_type} is not allowed")

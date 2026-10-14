"""Org-admin console: which membership roles may be assigned (server-side)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.service import record_audit
from app.core.roles import Role
from app.core.tenant import TenantContext

ORG_ADMIN_INVITE_ROLES = frozenset({Role.EDITOR, Role.VIEWER})

ORG_ADMIN_ASSIGN_FORBIDDEN_MESSAGE = (
    "Only the platform super admin can assign the Organization admin role."
)


class OrgAdminRoleAssignmentDenied(Exception):
    def __init__(self, *, code: str, message: str, attempted_role: str) -> None:
        self.code = code
        self.message = message
        self.attempted_role = attempted_role
        super().__init__(message)


def normalize_invite_role_raw(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "_")


def parse_org_admin_invite_role(raw: str) -> Role:
    """Parse role from invite payload; org-admin surface only allows Editor/Viewer."""
    normalized = normalize_invite_role_raw(raw)
    if not normalized:
        raise ValueError("MISSING_ROLE")
    if normalized in {"PLATFORM_ADMIN", "SUPER_ADMIN", "MASTER"}:
        raise ValueError("INVALID_ROLE")
    try:
        return Role(normalized)
    except ValueError as exc:
        raise ValueError("INVALID_ROLE") from exc


def record_role_assignment_denied(
    db: Session,
    *,
    tenant: TenantContext,
    attempted_role: str,
    context: str,
    resource_id: str | None = None,
) -> None:
    record_audit(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        action="role_assignment_denied",
        resource_type="organization_membership",
        resource_id=resource_id,
        metadata={
            "attempted_role": attempted_role,
            "context": context,
            "caller_role": tenant.role.value,
        },
    )


def assert_org_admin_may_assign_role(
    db: Session,
    tenant: TenantContext,
    role: Role,
    *,
    context: str,
    resource_id: str | None = None,
) -> None:
    """Org admins may invite/assign Editor and Viewer only (never ORG_ADMIN)."""
    if role == Role.ORG_ADMIN:
        record_role_assignment_denied(
            db,
            tenant=tenant,
            attempted_role=role.value,
            context=context,
            resource_id=resource_id,
        )
        db.flush()
        raise OrgAdminRoleAssignmentDenied(
            code="ORG_ADMIN_ASSIGN_FORBIDDEN",
            message=ORG_ADMIN_ASSIGN_FORBIDDEN_MESSAGE,
            attempted_role=role.value,
        )
    if role not in ORG_ADMIN_INVITE_ROLES:
        record_role_assignment_denied(
            db,
            tenant=tenant,
            attempted_role=role.value,
            context=context,
            resource_id=resource_id,
        )
        db.flush()
        raise OrgAdminRoleAssignmentDenied(
            code="INVALID_ROLE",
            message="Choose Editor or Viewer.",
            attempted_role=role.value,
        )


def assert_org_admin_may_remove_membership(
    db: Session,
    tenant: TenantContext,
    *,
    target_membership_id: UUID,
    target_role: str,
) -> None:
    if target_role == Role.ORG_ADMIN.value:
        record_audit(
            db,
            organization_id=tenant.organization_id,
            user_id=tenant.user_id,
            action="role_assignment_denied",
            resource_type="organization_membership",
            resource_id=str(target_membership_id),
            metadata={
                "attempted_action": "remove_org_admin",
                "context": "members_deactivate",
                "caller_role": tenant.role.value,
            },
        )
        db.flush()
        raise OrgAdminRoleAssignmentDenied(
            code="ORG_ADMIN_REMOVE_FORBIDDEN",
            message="Organization administrators can only be changed by the platform super admin.",
            attempted_role=Role.ORG_ADMIN.value,
        )

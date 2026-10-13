from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.roles import Role, role_at_least
from app.core.tenant import TenantContext
from app.models.access_group import AccessGroupMembership


@dataclass(frozen=True)
class UserAccessContext:
    user_id: UUID
    organization_id: UUID
    role: Role
    group_ids: tuple[UUID, ...]

    @property
    def is_org_admin(self) -> bool:
        return role_at_least(self.role, Role.ORG_ADMIN)


def build_access_context(db: Session, tenant: TenantContext) -> UserAccessContext:
    rows = (
        db.query(AccessGroupMembership.group_id)
        .filter(
            AccessGroupMembership.organization_id == tenant.organization_id,
            AccessGroupMembership.user_id == tenant.user_id,
        )
        .all()
    )
    group_ids = tuple(row[0] for row in rows)
    return UserAccessContext(
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
        role=tenant.role,
        group_ids=group_ids,
    )

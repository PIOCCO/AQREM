from dataclasses import dataclass
from uuid import UUID

from app.core.roles import Role


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    organization_id: UUID
    role: Role
    email: str

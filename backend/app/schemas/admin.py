from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.roles import Role
from app.models.enums import LicenseStatus


class AdminContextResponse(BaseModel):
    licensing_test_mode: bool
    test_mode_effective: bool
    active_super_admin_count: int = 0
    super_admin_warning: bool = False


class PlatformStaffRow(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    platform_role: str
    status: str
    created_at: datetime


class PlatformStaffInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(description="SUPER_ADMIN, PLATFORM_SUPPORT, or PLATFORM_BILLING")


class DeactivateMemberRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PlatformStaffRoleUpdate(BaseModel):
    role: str
    reason: str = Field(min_length=3, max_length=500)


class ReplaceOrgAdminRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=3, max_length=500)


class PermissionsMatrixResponse(BaseModel):
    permissions: list[str]
    roles: list[str]
    matrix: dict[str, dict[str, bool]]
    endpoints: dict[str, str]


class RolesAuditReport(BaseModel):
    issues: list[dict]
    summary: dict[str, int]


class SeatUsageResponse(BaseModel):
    active_members: int
    pending_invitations: int
    seats_used: int
    seats_limit: int
    seats_available: int
    is_full: bool


class AdminOrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    license_limit: int = Field(ge=1)
    environment: str = Field(description="production or test")
    owner_display_name: str | None = Field(default=None, max_length=255)


class AdminOrganizationUpdate(BaseModel):
    license_limit: int | None = Field(default=None, ge=0)
    license_status: LicenseStatus | None = None
    is_active: bool | None = None
    owner_display_name: str | None = None


class AdminOrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    license_limit: int
    license_status: str
    environment: str
    is_active: bool
    owner_display_name: str | None
    created_at: datetime
    license_renews_at: datetime | None
    seats: SeatUsageResponse


class AdminOrganizationListResponse(BaseModel):
    items: list[AdminOrganizationResponse]
    counts: dict[str, int]


class AdminProvisionUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.EDITOR


class AdminProvisionUserResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    email: EmailStr
    role: Role
    invitation_id: UUID
    invitation_expires_at: datetime
    invitation_setup_path: str
    invitation_setup_url: str


class AdminMembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    user_is_active: bool


class AdminInvitationResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: Role
    expires_at: datetime
    created_at: datetime


class AdminDirectoryRow(BaseModel):
    row_id: str
    kind: str
    membership_id: UUID | None = None
    invitation_id: UUID | None = None
    user_id: UUID | None = None
    full_name: str
    email: EmailStr
    role: Role
    status: str


class AdminDirectoryResponse(BaseModel):
    seats: SeatUsageResponse
    license_status: str
    license_renews_at: datetime | None
    rows: list[AdminDirectoryRow]
    total: int
    page: int
    page_size: int


class AdminAuditRow(BaseModel):
    id: UUID
    created_at: datetime
    actor_email: str | None
    action: str
    target: str


class AdminAuditListResponse(BaseModel):
    items: list[AdminAuditRow]


class AdminMemberRoleUpdate(BaseModel):
    role: Role


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)

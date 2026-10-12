from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.roles import Role
from app.models.enums import LicenseStatus


class AdminOrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, min_length=2, max_length=100)
    license_limit: int = Field(default=0, ge=0)
    license_status: LicenseStatus | None = None


class AdminOrganizationUpdate(BaseModel):
    license_limit: int | None = Field(default=None, ge=0)
    license_status: LicenseStatus | None = None
    is_active: bool | None = None


class AdminOrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    license_limit: int
    license_status: str
    is_active: bool
    active_seats: int


class AdminProvisionUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.EDITOR


class AdminProvisionUserResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    email: EmailStr
    role: Role
    invitation_expires_at: datetime
    invitation_setup_path: str


class AdminMembershipResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    user_is_active: bool


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)

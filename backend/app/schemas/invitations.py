from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.roles import Role


class AdminInvitationCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    personal_message: str | None = Field(default=None, max_length=2000)
    expires_days: int = Field(default=7, ge=1, le=14)


class InvitationLinkResponse(BaseModel):
    invitation_setup_path: str | None = None
    join_path: str | None = None
    expires_at: datetime | None = None


class AdminInvitationCreateResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    email: EmailStr
    role: Role
    invitation_id: UUID
    invitation_expires_at: datetime
    invitation_setup_path: str
    email_sent: bool


class AdminInvitationHistoryRow(BaseModel):
    id: UUID
    record_type: str = Field(description="admin_invitation or employee_link")
    kind: str
    email: str
    role: Role | None = None
    status: str
    invitee_full_name: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_by_user_id: UUID | None = None
    joined_count: int | None = None
    pending_approval_count: int | None = None


class EmployeeLinkCreateRequest(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list)
    require_admin_approval: bool | None = None
    max_joins: int | None = Field(default=None, ge=1)
    expires_days: int | None = Field(default=30, ge=1, le=90)


class EmployeeLinkCreateResponse(BaseModel):
    link_id: UUID
    join_path: str
    expires_at: datetime | None
    require_admin_approval: bool
    allowed_domains: list[str]
    max_joins: int | None
    email_delivery_configured: bool


class EmployeeLinkSummary(BaseModel):
    link_id: UUID | None
    status: str | None
    joined_count: int
    pending_approval_count: int
    max_joins: int | None
    expires_at: datetime | None
    allowed_domains: list[str]
    require_admin_approval: bool


class InvitationsSetupStatus(BaseModel):
    admin_invitation_status: str
    admin_invitation_email: str | None
    admin_accepted: bool
    employee_link_status: str | None
    employee_link_joined_count: int
    employee_link_pending_count: int
    seats: dict


class JoinPreviewRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class JoinPreviewResponse(BaseModel):
    organization_name: str


class JoinStartRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)


class JoinStartResponse(BaseModel):
    pending_id: UUID
    verification_required: bool
    dev_verification_code: str | None = None


class JoinVerifyRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    pending_id: UUID
    code: str = Field(min_length=4, max_length=12)


class JoinVerifyResponse(BaseModel):
    pending_id: UUID
    next_step: str


class JoinCompleteRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    pending_id: UUID
    password: str = Field(min_length=8, max_length=256)


class JoinCompleteResponse(BaseModel):
    status: str
    organization_id: UUID | None = None
    access_token: str | None = None


class AcceptInvitationPreviewRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class AcceptInvitationPreviewResponse(BaseModel):
    organization_name: str
    role: Role
    email: EmailStr
    invitee_full_name: str | None

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.roles import Role


class LoginRequest(BaseModel):
    """Login email is normalized; dev/lab addresses (.local) are allowed."""

    email: str = Field(min_length=3, max_length=320)
    password: str
    organization_id: UUID | None = None

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Enter a valid email address")
        return email


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization_id: UUID | None = None
    role: Role | None = None
    must_change_password: bool = False
    is_platform_admin: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if "@" not in email:
            raise ValueError("Enter a valid email address")
        return email


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class UserResponse(BaseModel):
    id: UUID
    email: str = Field(min_length=3, max_length=320)
    full_name: str
    organization_id: UUID | None = None
    role: Role | None = None
    platform_role: str | None = None
    is_platform_admin: bool = False
    must_change_password: bool = False
    permissions: list[str] = []

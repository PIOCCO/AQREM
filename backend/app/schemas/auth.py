from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.core.roles import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization_id: UUID | None = None
    role: Role | None = None
    must_change_password: bool = False
    is_platform_admin: bool = False


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    organization_id: UUID | None = None
    role: Role | None = None
    is_platform_admin: bool = False
    must_change_password: bool = False

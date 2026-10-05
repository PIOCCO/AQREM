from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.core.roles import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    organization_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    organization_id: UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    organization_id: UUID
    role: Role


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    organization_id: UUID
    role: Role

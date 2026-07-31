"""Auth service - Pydantic schemas (contracts with frontend)."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


# ─── Request schemas ─────────────────────────────────────────

class LoginRequest(BaseModel):
    identifier: str  # username or email
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    fullName: str
    role: str | None = "user"


class ValidateTokenRequest(BaseModel):
    token: str


# ─── Response schemas ────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    fullName: str
    role: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            fullName=user.full_name,
            role=user.role,
        )


class LoginResponse(BaseModel):
    token: str                          # access_token de Keycloak (o JWT legacy)
    refresh_token: str = ""             # Keycloak refresh token
    user: UserOut


class ValidateTokenResponse(BaseModel):
    valid: bool
    sub: str = ""
    email: str = ""
    tenant_slug: str = ""
    roles: list[str] = []

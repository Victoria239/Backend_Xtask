"""Tenants service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=2, max_length=255)
    domain: str | None = None
    plan: str = "startup"
    settings: dict = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    plan: str | None = None
    is_active: bool | None = None
    settings: dict | None = None


class TenantOut(BaseModel):
    id: int
    slug: str
    name: str
    domain: str | None
    plan: str
    is_active: bool
    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantMembershipCreate(BaseModel):
    tenant_id: int
    user_id: int
    role: str = "member"
    is_default: bool = False


class TenantMembershipOut(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    role: str
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}

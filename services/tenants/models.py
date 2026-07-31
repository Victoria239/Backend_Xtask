"""Tenants service - multi-tenant SQLAlchemy models (P-01)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Tenant(Base):
    """A tenant represents a customer organization with isolated data and corpus."""

    __tablename__ = "tenants"
    __table_args__ = {"schema": "svc_tenants"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="startup")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantMembership(Base):
    """Link a user to a tenant with a role inside that tenant."""

    __tablename__ = "tenant_memberships"
    __table_args__ = {"schema": "svc_tenants"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Tenants service - data access layer."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.tenants.models import Tenant, TenantMembership


class TenantRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, tenant_id: int) -> Tenant | None:
        res = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return res.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        res = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return res.scalar_one_or_none()

    async def list_all(self, only_active: bool = True) -> list[Tenant]:
        stmt = select(Tenant)
        if only_active:
            stmt = stmt.where(Tenant.is_active.is_(True))
        res = await self.db.execute(stmt.order_by(Tenant.id))
        return list(res.scalars().all())

    async def create(self, **fields) -> Tenant:
        tenant = Tenant(**fields)
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def update(self, tenant_id: int, **fields) -> Tenant | None:
        tenant = await self.get(tenant_id)
        if not tenant:
            return None
        for k, v in fields.items():
            if v is not None:
                setattr(tenant, k, v)
        await self.db.flush()
        return tenant

    async def list_user_memberships(self, user_id: int) -> list[TenantMembership]:
        res = await self.db.execute(
            select(TenantMembership).where(TenantMembership.user_id == user_id)
        )
        return list(res.scalars().all())

    async def get_default_tenant_for_user(self, user_id: int) -> Tenant | None:
        res = await self.db.execute(
            select(Tenant)
            .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
            .where(TenantMembership.user_id == user_id)
            .order_by(TenantMembership.is_default.desc(), TenantMembership.id.asc())
            .limit(1)
        )
        return res.scalar_one_or_none()

    async def add_membership(self, tenant_id: int, user_id: int, role: str = "member", is_default: bool = False) -> TenantMembership:
        membership = TenantMembership(
            tenant_id=tenant_id, user_id=user_id, role=role, is_default=is_default,
        )
        self.db.add(membership)
        await self.db.flush()
        return membership

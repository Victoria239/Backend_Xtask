"""Tenants service - business logic."""

from shared.exceptions import NotFoundException, ConflictException
from services.tenants.repository import TenantRepository
from services.tenants.schemas import TenantCreate, TenantUpdate


class TenantService:
    def __init__(self, repo: TenantRepository):
        self.repo = repo

    async def list_tenants(self):
        return await self.repo.list_all(only_active=False)

    async def get_tenant(self, tenant_id: int):
        tenant = await self.repo.get(tenant_id)
        if not tenant:
            raise NotFoundException("Tenant", tenant_id)
        return tenant

    async def get_tenant_by_slug(self, slug: str):
        tenant = await self.repo.get_by_slug(slug)
        if not tenant:
            raise NotFoundException("Tenant", slug)
        return tenant

    async def create_tenant(self, data: TenantCreate):
        if await self.repo.get_by_slug(data.slug):
            raise ConflictException(f"Tenant slug '{data.slug}' already exists")
        return await self.repo.create(**data.model_dump())

    async def update_tenant(self, tenant_id: int, data: TenantUpdate):
        tenant = await self.repo.update(tenant_id, **data.model_dump(exclude_unset=True))
        if not tenant:
            raise NotFoundException("Tenant", tenant_id)
        return tenant

    async def add_member(self, tenant_id: int, user_id: int, role: str = "member", is_default: bool = False):
        await self.get_tenant(tenant_id)
        return await self.repo.add_membership(tenant_id, user_id, role, is_default)

    async def list_user_memberships(self, user_id: int):
        return await self.repo.list_user_memberships(user_id)

    async def get_default_tenant_for_user(self, user_id: int):
        return await self.repo.get_default_tenant_for_user(user_id)

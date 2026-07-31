"""Tenants service - HTTP routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_user, require_admin, CurrentUser
from services.tenants.repository import TenantRepository
from services.tenants.service import TenantService
from services.tenants.schemas import (
    TenantCreate,
    TenantUpdate,
    TenantOut,
    TenantMembershipCreate,
    TenantMembershipOut,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("tenants"))) -> TenantService:
    return TenantService(TenantRepository(db))


@router.get("", response_model=list[TenantOut], dependencies=[Depends(require_admin)])
async def list_tenants(service: TenantService = Depends(get_service)):
    return await service.list_tenants()


@router.post("", response_model=TenantOut, dependencies=[Depends(require_admin)])
async def create_tenant(data: TenantCreate, service: TenantService = Depends(get_service)):
    return await service.create_tenant(data)


@router.get("/me", response_model=list[TenantMembershipOut])
async def list_my_memberships(
    service: TenantService = Depends(get_service),
    user: CurrentUser = Depends(get_current_user),
):
    return await service.list_user_memberships(user.id)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: int,
    service: TenantService = Depends(get_service),
    user: CurrentUser = Depends(get_current_user),
):
    return await service.get_tenant(tenant_id)


@router.patch("/{tenant_id}", response_model=TenantOut, dependencies=[Depends(require_admin)])
async def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    service: TenantService = Depends(get_service),
):
    return await service.update_tenant(tenant_id, data)


@router.post("/{tenant_id}/members", response_model=TenantMembershipOut, dependencies=[Depends(require_admin)])
async def add_member(
    tenant_id: int,
    data: TenantMembershipCreate,
    service: TenantService = Depends(get_service),
):
    return await service.add_member(tenant_id, data.user_id, data.role, data.is_default)

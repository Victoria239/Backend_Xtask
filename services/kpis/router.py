"""KPIs service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id
from services.kpis.repository import KpiRepository
from services.kpis.service import KpiService
from services.kpis.schemas import (
    KpiCreate, KpiUpdate, KpiOut, KpiResultUpdate, KpiValidate,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> KpiService:
    return KpiService(KpiRepository(db))


@router.get("", response_model=list[KpiOut])
async def list_kpis(
    employee_id: int | None = Query(None),
    period: str | None = Query(None),
    status: str | None = Query(None),
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if employee_id:
        filters["employee_id"] = employee_id
    if period:
        filters["period"] = period
    if status:
        filters["status"] = status
    return await service.list_kpis(filters if filters else None)


@router.get("/{kpi_id}", response_model=KpiOut)
async def get_kpi(
    kpi_id: int,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_kpi(kpi_id)


@router.post("", response_model=KpiOut)
async def create_kpi(
    data: KpiCreate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_kpi(data)


@router.patch("/{kpi_id}", response_model=KpiOut)
async def update_kpi(
    kpi_id: int,
    data: KpiUpdate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_kpi(kpi_id, data)


@router.patch("/{kpi_id}/resultado", response_model=KpiOut)
async def evaluate_kpi(
    kpi_id: int,
    data: KpiResultUpdate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.evaluate_kpi(kpi_id, data.actual_value)


@router.patch("/{kpi_id}/validar", response_model=KpiOut)
async def validate_kpi(
    kpi_id: int,
    data: KpiValidate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.validate_kpi(kpi_id, data.validated)


@router.delete("/{kpi_id}", status_code=204)
async def delete_kpi(
    kpi_id: int,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_kpi(kpi_id)

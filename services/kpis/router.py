"""KPIs service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_user_id,
    get_optional_tenant_id,
    require_admin,
    require_manager,
)
from services.kpis.repository import KpiRepository
from services.kpis.service import KpiService
from services.kpis.schemas import (
    KpiCreate,
    KpiMeasurementBatch,
    KpiMeasurementIngestResponse,
    KpiMeasurementOut,
    KpiOut,
    KpiResultUpdate,
    KpiUpdate,
    KpiValidate,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("kpis"))) -> KpiService:
    return KpiService(KpiRepository(db))


@router.get("")
async def list_kpis(
    employee_id: int | None = Query(None),
    period: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
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
    return await service.list_kpis_paginated(filters if filters else None, page, page_size)


@router.get("/{kpi_id}", response_model=KpiOut)
async def get_kpi(
    kpi_id: int,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_kpi(kpi_id)


@router.post("", response_model=KpiOut, dependencies=[Depends(require_manager)])
async def create_kpi(
    data: KpiCreate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_kpi(data)


@router.patch("/{kpi_id}", response_model=KpiOut, dependencies=[Depends(require_manager)])
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


@router.patch("/{kpi_id}/validar", response_model=KpiOut, dependencies=[Depends(require_admin)])
async def validate_kpi(
    kpi_id: int,
    data: KpiValidate,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.validate_kpi(kpi_id, data.validated)


@router.delete("/{kpi_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_kpi(
    kpi_id: int,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_kpi(kpi_id)


# ─── C-01: measurement ingestion API ────────────────────────────
@router.post(
    "/measurements",
    response_model=KpiMeasurementIngestResponse,
    dependencies=[Depends(require_manager)],
)
async def ingest_measurements(
    payload: KpiMeasurementBatch,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
    tenant_id: int | None = Depends(get_optional_tenant_id),
):
    return await service.ingest_measurements(tenant_id, payload.measurements)


@router.get("/{kpi_id}/measurements", response_model=list[KpiMeasurementOut])
async def list_kpi_measurements(
    kpi_id: int,
    service: KpiService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_measurements(kpi_id)

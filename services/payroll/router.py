"""Payroll service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id
from services.payroll.repository import PayrollRepository
from services.payroll.service import PayrollService
from services.payroll.schemas import (
    PayrollCreate, PayrollUpdate, PayrollOut, PayrollStatusUpdate,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> PayrollService:
    return PayrollService(PayrollRepository(db))


@router.get("", response_model=list[PayrollOut])
async def list_payrolls(
    employee_id: int | None = Query(None),
    period: str | None = Query(None),
    status: str | None = Query(None),
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if employee_id:
        filters["employee_id"] = employee_id
    if period:
        filters["period"] = period
    if status:
        filters["status"] = status
    return await service.list_payrolls(filters if filters else None)


@router.get("/metricas")
async def get_metrics(
    period: str | None = Query(None),
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {"period": period} if period else None
    return await service.get_metrics(filters)


@router.get("/{payroll_id}", response_model=PayrollOut)
async def get_payroll(
    payroll_id: int,
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_payroll(payroll_id)


@router.post("", response_model=PayrollOut)
async def create_payroll(
    data: PayrollCreate,
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_payroll(data)


@router.patch("/{payroll_id}", response_model=PayrollOut)
async def update_payroll(
    payroll_id: int,
    data: PayrollUpdate,
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_payroll(payroll_id, data)


@router.patch("/{payroll_id}/estado", response_model=PayrollOut)
async def change_payroll_status(
    payroll_id: int,
    data: PayrollStatusUpdate,
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.change_status(payroll_id, data.status)


@router.delete("/{payroll_id}", status_code=204)
async def delete_payroll(
    payroll_id: int,
    service: PayrollService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_payroll(payroll_id)

"""Leaves service — HTTP routes (H-04)."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_admin, require_manager,
)
from services.leaves.repository import LeavesRepository
from services.leaves.schemas import (
    BalanceAdjustment, BalanceOut, LeaveDecision, LeaveEventOut, LeaveIn,
    LeaveOut, LeaveSummary, LeaveTypeIn, LeaveTypeOut, LeaveUpdate,
)
from services.leaves.service import LeavesService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("leaves"))) -> LeavesService:
    return LeavesService(LeavesRepository(db))


# ─── Leave Types ────────────────────────────────────────
@router.get("/types", response_model=list[LeaveTypeOut])
async def list_types(
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_types(tenant_id)


@router.post("/types", response_model=LeaveTypeOut, dependencies=[Depends(require_admin)])
async def create_type(
    payload: LeaveTypeIn,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.create_type(tenant_id, payload)


@router.put(
    "/types/{type_id}", response_model=LeaveTypeOut, dependencies=[Depends(require_admin)]
)
async def update_type(
    type_id: int, payload: LeaveTypeIn,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    out = await service.update_type(tenant_id, type_id, payload)
    if not out:
        raise HTTPException(status_code=404, detail="Tipo no encontrado")
    return out


# ─── Leaves ────────────────────────────────────────
@router.get("/", response_model=list[LeaveSummary])
async def list_leaves(
    employee_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_leaves(
        tenant_id, employee_id=employee_id, status=status,
        date_from=date_from, date_to=date_to,
    )


@router.get("/{leave_id}", response_model=LeaveOut)
async def get_leave(
    leave_id: int,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    out = await service.get_leave(tenant_id, leave_id)
    if not out:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return out


@router.get("/{leave_id}/events", response_model=list[LeaveEventOut])
async def list_events(
    leave_id: int,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.list_events(tenant_id, leave_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/employee/{employee_id}", response_model=LeaveOut)
async def request_leave(
    employee_id: int, payload: LeaveIn,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.request_leave(tenant_id, employee_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{leave_id}", response_model=LeaveOut)
async def update_leave(
    leave_id: int, payload: LeaveUpdate,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        out = await service.update_leave(tenant_id, leave_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not out:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return out


@router.post(
    "/{leave_id}/decision", response_model=LeaveOut, dependencies=[Depends(require_manager)]
)
async def decide(
    leave_id: int, payload: LeaveDecision,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.decide(tenant_id, leave_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{leave_id}/cancel", response_model=LeaveOut)
async def cancel(
    leave_id: int,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.cancel(tenant_id, leave_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ─── Balances ────────────────────────────────────────
@router.get("/employee/{employee_id}/balances", response_model=list[BalanceOut])
async def list_balances(
    employee_id: int,
    year: int = Query(...),
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_balances(tenant_id, employee_id, year)


@router.post(
    "/employee/{employee_id}/balances/{type_id}/adjust",
    response_model=BalanceOut, dependencies=[Depends(require_manager)],
)
async def adjust_balance(
    employee_id: int, type_id: int,
    year: int = Query(...),
    payload: BalanceAdjustment = ...,
    service: LeavesService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.adjust_balance(tenant_id, employee_id, type_id, year, payload, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

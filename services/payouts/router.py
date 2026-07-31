"""Payouts service — HTTP routes (C-04)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_admin, require_manager,
)
from services.payouts.repository import PayoutsRepository
from services.payouts.schemas import (
    PayoutOut, RunDetail, RunIn, RunStatusUpdate, RunSummary,
)
from services.payouts.service import PayoutsService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("payouts"))) -> PayoutsService:
    return PayoutsService(PayoutsRepository(db))


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    status: str | None = Query(None),
    service: PayoutsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_runs(tenant_id, status)


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(
    run_id: int,
    service: PayoutsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.get_run_detail(tenant_id, run_id)
    if not d:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    return d


@router.post("/runs/compute", response_model=RunDetail, dependencies=[Depends(require_manager)])
async def compute_run(
    payload: RunIn,
    service: PayoutsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.compute_run(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/runs/{run_id}/status", response_model=RunDetail, dependencies=[Depends(require_manager)]
)
async def update_status(
    run_id: int, payload: RunStatusUpdate,
    service: PayoutsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.update_status(tenant_id, user_id, run_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/runs/{run_id}", dependencies=[Depends(require_admin)])
async def delete_run(
    run_id: int,
    service: PayoutsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        ok = await service.delete_run(tenant_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="Run no encontrado")
    return {"ok": True}

"""Plans service — HTTP routes (C-03)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    require_admin,
    require_manager,
)
from services.plans.repository import PlanRepository
from services.plans.schemas import (
    PlanDetail,
    PlanIn,
    PlanSummary,
    PlanUpdate,
    RuleIn,
    RuleOut,
    SimulateRequest,
    SimulateResponse,
)
from services.plans.service import PlanService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("plans"))) -> PlanService:
    return PlanService(PlanRepository(db))


@router.get("/", response_model=list[PlanSummary])
async def list_plans(
    active: bool | None = Query(None),
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_plans(tenant_id, active)


@router.get("/{plan_id}", response_model=PlanDetail)
async def get_plan(
    plan_id: int,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.get_plan_detail(tenant_id, plan_id)
    if not d:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return d


@router.post("/", response_model=PlanDetail, dependencies=[Depends(require_manager)])
async def create_plan(
    payload: PlanIn,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.create_plan(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{plan_id}", response_model=PlanDetail, dependencies=[Depends(require_manager)])
async def update_plan(
    plan_id: int,
    payload: PlanUpdate,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.update_plan(tenant_id, plan_id, payload)
    if not d:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return d


@router.delete("/{plan_id}", dependencies=[Depends(require_admin)])
async def delete_plan(
    plan_id: int,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_plan(tenant_id, plan_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return {"ok": True}


@router.post("/{plan_id}/rules", response_model=RuleOut, dependencies=[Depends(require_manager)])
async def add_rule(
    plan_id: int,
    payload: RuleIn,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.add_rule(tenant_id, plan_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/rules/{rule_id}", response_model=RuleOut, dependencies=[Depends(require_manager)])
async def update_rule(
    rule_id: int,
    payload: RuleIn,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        out = await service.update_rule(tenant_id, rule_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not out:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return out


@router.delete("/rules/{rule_id}", dependencies=[Depends(require_manager)])
async def delete_rule(
    rule_id: int,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_rule(tenant_id, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {"ok": True}


@router.post("/{plan_id}/simulate", response_model=SimulateResponse)
async def simulate(
    plan_id: int,
    payload: SimulateRequest,
    service: PlanService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.simulate(tenant_id, user_id, plan_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

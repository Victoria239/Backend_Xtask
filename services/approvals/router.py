"""Approvals service — HTTP routes (C-05)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_admin, require_manager,
)
from services.approvals.schemas import (
    FlowDetail, FlowIn, FlowOut, InstanceDetail, InstanceSummary,
    StartInstance, StepDecision,
)
from services.approvals.service import ApprovalsService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("approvals"))) -> ApprovalsService:
    return ApprovalsService(db)


# ─── Flows ───────────────────────────────────────────
@router.get("/flows", response_model=list[FlowOut])
async def list_flows(
    target_kind: str | None = Query(None),
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_flows(tenant_id, target_kind)


@router.get("/flows/{flow_id}", response_model=FlowDetail)
async def get_flow(
    flow_id: int,
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.get_flow_detail(tenant_id, flow_id)
    if not d:
        raise HTTPException(status_code=404, detail="Flow no encontrado")
    return d


@router.post("/flows", response_model=FlowDetail, dependencies=[Depends(require_admin)])
async def create_flow(
    payload: FlowIn,
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.create_flow(tenant_id, payload)


# ─── Instances ───────────────────────────────────────
@router.get("/instances", response_model=list[InstanceSummary])
async def list_instances(
    status: str | None = Query(None),
    mine: bool = Query(False, description="Si true, solo las que YO debo aprobar"),
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_instances(
        tenant_id, status=status, approver_user_id=user_id if mine else None,
    )


@router.get("/instances/{instance_id}", response_model=InstanceDetail)
async def get_instance(
    instance_id: int,
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.get_instance_detail(tenant_id, instance_id)
    if not d:
        raise HTTPException(status_code=404, detail="Instance no encontrada")
    return d


@router.post(
    "/instances", response_model=InstanceDetail, dependencies=[Depends(require_manager)]
)
async def start_instance(
    payload: StartInstance,
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.start_instance(tenant_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/instances/{instance_id}/decision", response_model=InstanceDetail)
async def decide(
    instance_id: int, payload: StepDecision,
    service: ApprovalsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.decide(tenant_id, user_id, instance_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

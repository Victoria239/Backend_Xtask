"""Tasks service — HTTP routes (Tablero de Actividades)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_manager,
)
from services.tasks.repository import TasksRepository
from services.tasks.schemas import (
    ActivityIn, ActivityOut, ActivityUpdate, BoardMetrics, BoardView, MoveActivity,
)
from services.tasks.service import TasksService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("tasks"))) -> TasksService:
    return TasksService(TasksRepository(db))


# ─── Board ────────────────────────────────────────
@router.get("/board", response_model=BoardView)
async def get_board(
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.board(tenant_id)


@router.get("/metricas", response_model=BoardMetrics)
async def get_metrics(
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.metrics(tenant_id)


# ─── Activities (backlog) ────────────────────────────────────────
@router.get("", response_model=list[ActivityOut])
async def list_activities(
    status: str | None = Query(None),
    assignee_employee_id: int | None = Query(None),
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_activities(tenant_id, status, assignee_employee_id)


@router.post("", response_model=ActivityOut, dependencies=[Depends(require_manager)])
async def create_activity(
    payload: ActivityIn,
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.create_activity(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{activity_id}", response_model=ActivityOut)
async def get_activity(
    activity_id: int,
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    a = await service.get_activity(tenant_id, activity_id)
    if not a:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return a


@router.patch("/{activity_id}", response_model=ActivityOut, dependencies=[Depends(require_manager)])
async def update_activity(
    activity_id: int, payload: ActivityUpdate,
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        a = await service.update_activity(tenant_id, activity_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not a:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return a


@router.post("/{activity_id}/mover", response_model=ActivityOut, dependencies=[Depends(require_manager)])
async def move_activity(
    activity_id: int, payload: MoveActivity,
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        a = await service.move_activity(tenant_id, activity_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not a:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return a


@router.delete("/{activity_id}", dependencies=[Depends(require_manager)])
async def delete_activity(
    activity_id: int,
    service: TasksService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_activity(tenant_id, activity_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Actividad no encontrada")
    return {"ok": True}

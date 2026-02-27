"""Dashboard service - API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id
from services.dashboard.repository import LayoutRepository, WidgetRepository
from services.dashboard.service import DashboardService
from services.dashboard.schemas import (
    LayoutCreate, LayoutUpdate, LayoutOut,
    WidgetCreate, WidgetUpdate, WidgetOut, WidgetPositionUpdate,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(LayoutRepository(db), WidgetRepository(db))


# ─── Layouts ────────────────────────────────────────────────

@router.get("/layouts", response_model=list[LayoutOut])
async def get_user_layouts(
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_layouts(user_id)


@router.get("/layouts/default")
async def get_default_layout(
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    layout = await service.get_default_layout(user_id)
    return layout or {}


@router.get("/layouts/{layout_id}", response_model=LayoutOut)
async def get_layout(
    layout_id: int,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_layout(layout_id)


@router.post("/layouts", response_model=LayoutOut)
async def create_layout(
    data: LayoutCreate,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_layout(user_id, data)


@router.patch("/layouts/{layout_id}", response_model=LayoutOut)
async def update_layout(
    layout_id: int,
    data: LayoutUpdate,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_layout(layout_id, data)


@router.delete("/layouts/{layout_id}", status_code=204)
async def delete_layout(
    layout_id: int,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_layout(layout_id)


@router.post("/layouts/{layout_id}/default", response_model=LayoutOut)
async def set_default_layout(
    layout_id: int,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.set_default(user_id, layout_id)


# ─── Widgets ────────────────────────────────────────────────

@router.get("/layouts/{layout_id}/widgets", response_model=list[WidgetOut])
async def list_widgets(
    layout_id: int,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_widgets(layout_id)


@router.post("/layouts/{layout_id}/widgets", response_model=WidgetOut)
async def add_widget(
    layout_id: int,
    data: WidgetCreate,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.add_widget(layout_id, data)


@router.patch("/layouts/{layout_id}/widgets/{widget_id}", response_model=WidgetOut)
async def update_widget(
    layout_id: int,
    widget_id: int,
    data: WidgetUpdate,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_widget(widget_id, data)


@router.delete("/layouts/{layout_id}/widgets/{widget_id}", status_code=204)
async def remove_widget(
    layout_id: int,
    widget_id: int,
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.remove_widget(widget_id)


@router.patch("/layouts/{layout_id}/positions", response_model=list[WidgetOut])
async def update_positions(
    layout_id: int,
    data: list[WidgetPositionUpdate],
    service: DashboardService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_positions(layout_id, data)

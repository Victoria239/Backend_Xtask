"""Dashboard service - API routes.

Handles: /api/dashboard/*
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


@router.get("/layouts")
async def get_user_layouts(user_id: int = Depends(get_current_user_id)):
    # TODO: Implement in feature/dashboard-service
    return []


@router.get("/layouts/default")
async def get_default_layout(user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/layouts/{layout_id}")
async def get_layout(layout_id: str, user_id: int = Depends(get_current_user_id)):
    return {"id": layout_id}


@router.post("/layouts")
async def create_layout(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": "0"}


@router.patch("/layouts/{layout_id}")
async def update_layout(layout_id: str, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": layout_id}


@router.delete("/layouts/{layout_id}", status_code=204)
async def delete_layout(layout_id: str, user_id: int = Depends(get_current_user_id)):
    return None


@router.post("/layouts/{layout_id}/default")
async def set_default_layout(layout_id: str, user_id: int = Depends(get_current_user_id)):
    return {"id": layout_id}


@router.post("/layouts/{layout_id}/widgets")
async def add_widget(layout_id: str, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": "0"}


@router.patch("/layouts/{layout_id}/widgets/{widget_id}")
async def update_widget(layout_id: str, widget_id: str, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": widget_id}


@router.delete("/layouts/{layout_id}/widgets/{widget_id}", status_code=204)
async def remove_widget(layout_id: str, widget_id: str, user_id: int = Depends(get_current_user_id)):
    return None


@router.patch("/layouts/{layout_id}/positions")
async def update_positions(layout_id: str, data: dict, user_id: int = Depends(get_current_user_id)):
    return []

"""Skills service - API routes.

Handles: /api/habilidades/*
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


@router.get("/mis-habilidades")
async def get_mis_habilidades(user_id: int = Depends(get_current_user_id)):
    # TODO: Implement in feature/skills-service
    return {}


@router.get("/{target_user_id}")
async def get_habilidades_by_user(target_user_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.post("")
async def create_habilidad(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/{habilidad_id}")
async def update_habilidad(habilidad_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": habilidad_id}


@router.delete("/{habilidad_id}", status_code=204)
async def delete_habilidad(habilidad_id: int, user_id: int = Depends(get_current_user_id)):
    return None

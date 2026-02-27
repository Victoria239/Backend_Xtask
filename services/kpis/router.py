"""KPIs service - API routes.

Handles: /api/kpis/*
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


@router.get("/mis-kpis")
async def get_mis_kpis(
    mes: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/kpis-service
    return []


@router.get("/empleados")
async def get_empleados_kpis(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/empleado-por-userid/{target_user_id}")
async def get_empleado_by_userid(target_user_id: int, user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/bonificacion")
async def get_bonificacion(
    id: int | None = Query(None),
    mes: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return {}


@router.get("/bonificaciones/historial")
async def get_bonificaciones_historial(
    limit: int | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return []


@router.get("/{kpi_id}")
async def get_kpi(kpi_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": kpi_id}


@router.post("")
async def create_kpi(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/{kpi_id}")
async def update_kpi(kpi_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": kpi_id}


@router.delete("/{kpi_id}")
async def delete_kpi(kpi_id: int, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


@router.patch("/{kpi_id}/resultado")
async def evaluar_kpi(kpi_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": kpi_id}


@router.patch("/{kpi_id}/validar")
async def validar_kpi(kpi_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": kpi_id}


@router.post("/calcular-bonificacion")
async def calcular_bonificacion(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.patch("/bonificacion/{bonificacion_id}/aprobar")
async def aprobar_bonificacion(bonificacion_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": bonificacion_id}


@router.patch("/bonificacion/{bonificacion_id}/marcar-pagada")
async def marcar_pagada(bonificacion_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": bonificacion_id}

"""Employees service - API routes.

Handles multiple frontend endpoint patterns:
- /api/empleados-nomina/*
- /api/empleados-nuevos/*
- /api/finanzas/nomina/empleados/*
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


# ─── /api/empleados-nomina ───────────────────────────────────

@router.get("/api/empleados-nomina")
async def list_empleados_nomina(
    proyectoId: int | None = Query(None),
    q: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return []


@router.post("/api/empleados-nomina")
async def create_empleado_nomina(
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": 0, "message": "Not implemented yet"}


@router.post("/api/empleados-nomina/{empleado_id}/contrato")
async def upload_contrato(
    empleado_id: int,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement file upload in feature/employees-service
    return {"message": "Not implemented yet"}


# ─── /api/empleados-nuevos ───────────────────────────────────

@router.get("/api/empleados-nuevos/{empleado_id}")
async def get_empleado(
    empleado_id: int,
    include: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": empleado_id}


@router.put("/api/empleados-nuevos/{empleado_id}")
async def update_empleado(
    empleado_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": empleado_id}


@router.put("/api/empleados-nuevos/{empleado_id}/proyectos")
async def update_empleado_proyectos(
    empleado_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"success": True}


@router.delete("/api/empleados-nuevos/{empleado_id}")
async def delete_empleado(
    empleado_id: int,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"success": True, "message": "Not implemented yet"}


@router.get("/api/empleados-nuevos/{empleado_id}/historial-nomina")
async def get_historial_nomina(
    empleado_id: int,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return []


@router.patch("/api/empleados-nuevos/{empleado_id}/historial-nomina/{nomina_id}/estado")
async def update_estado_nomina(
    empleado_id: int,
    nomina_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"success": True}


# ─── /api/finanzas/nomina/empleados ──────────────────────────

@router.get("/api/finanzas/nomina/empleados")
async def list_empleados_finanzas(
    page: int = Query(1),
    pageSize: int = Query(10),
    contractStatus: str | None = Query(None),
    department: str | None = Query(None),
    search: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"data": [], "pagination": {"page": page, "pageSize": pageSize, "totalItems": 0, "totalPages": 0}}


@router.get("/api/finanzas/nomina/empleados/{empleado_id}")
async def get_empleado_finanzas(
    empleado_id: int,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": empleado_id}


@router.post("/api/finanzas/nomina/empleados")
async def create_empleado_finanzas(
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": 0}


@router.patch("/api/finanzas/nomina/empleados/{empleado_id}")
async def update_empleado_finanzas(
    empleado_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": empleado_id}


@router.patch("/api/finanzas/nomina/empleados/{empleado_id}/estado")
async def change_estado_empleado(
    empleado_id: int,
    data: dict,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"id": empleado_id}


@router.delete("/api/finanzas/nomina/empleados/{empleado_id}")
async def delete_empleado_finanzas(
    empleado_id: int,
    user_id: int = Depends(get_current_user_id),
):
    # TODO: Implement in feature/employees-service
    return {"message": "Not implemented yet", "empleado": {"id": empleado_id}}

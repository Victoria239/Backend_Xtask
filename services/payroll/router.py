"""Payroll service - API routes.

Handles multiple frontend endpoint patterns:
- /api/nominas/*
- /api/nominas-preview/*
- /api/nomina/*
- /api/finanzas/nomina/*
- /api/finances/payrolls/*
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# /api/finances/payrolls
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finances/payrolls")
async def list_payrolls(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/finances/payrolls/{payroll_id}")
async def get_payroll(payroll_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": payroll_id}


@router.post("/api/finances/payrolls")
async def create_payroll(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/finances/payrolls/{payroll_id}")
async def update_payroll(payroll_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": payroll_id}


@router.patch("/api/finances/payrolls/{payroll_id}/status")
async def update_payroll_status(payroll_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": payroll_id}


@router.post("/api/finances/payrolls/{payroll_id}/payment")
async def record_payroll_payment(payroll_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


@router.post("/api/finances/payrolls/calculate")
async def calculate_salary(data: dict, user_id: int = Depends(get_current_user_id)):
    return {}


@router.get("/api/finances/payrolls/{payroll_id}/pdf")
async def get_payroll_pdf(payroll_id: int, user_id: int = Depends(get_current_user_id)):
    return {"url": ""}


@router.post("/api/finances/payrolls/generate-batch")
async def generate_batch_payroll(data: dict, user_id: int = Depends(get_current_user_id)):
    return []


# ═══════════════════════════════════════════════════════════════
# /api/nomina
# ═══════════════════════════════════════════════════════════════

@router.get("/api/nomina/proyectos")
async def get_nomina_proyectos(user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/nomina/metricas")
async def get_nomina_metricas(
    proyectoId: int | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return {"totalMensual": 0, "pendientePago": 0, "pagadoMes": 0, "recursosActivos": 0}


@router.get("/api/nomina/recurso/{recurso_id}/historial")
async def get_recurso_historial(recurso_id: int, user_id: int = Depends(get_current_user_id)):
    return []


@router.get("/api/nomina/{proyecto_id}")
async def get_nomina_proyecto(
    proyecto_id: int,
    mes: str | None = Query(None),
    estado: str | None = Query(None),
    perfil: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return []


@router.get("/api/nomina/{proyecto_id}/resumen")
async def get_nomina_resumen(
    proyecto_id: int,
    mes: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
):
    return {}


@router.post("/api/nomina/{proyecto_id}/pagar")
async def registrar_pago_nomina(proyecto_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.patch("/api/nomina/{nomina_id}/estado")
async def update_nomina_estado(nomina_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": nomina_id}


# ═══════════════════════════════════════════════════════════════
# /api/finanzas/nomina
# ═══════════════════════════════════════════════════════════════

@router.get("/api/finanzas/nomina")
async def list_nominas_finanzas(
    empleadoId: int | None = Query(None),
    empleadoNombre: str | None = Query(None),
    mes: int | None = Query(None),
    anio: int | None = Query(None),
    estado: str | None = Query(None),
    periodo: str | None = Query(None),
    page: int = Query(1),
    pageSize: int = Query(10),
    user_id: int = Depends(get_current_user_id),
):
    return {
        "nominas": [],
        "pagination": {"page": page, "pageSize": pageSize, "totalItems": 0, "totalPages": 0},
    }


@router.get("/api/finanzas/nomina/{nomina_id}")
async def get_nomina_finanzas(nomina_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": nomina_id}


@router.post("/api/finanzas/nomina/cambiar-estado/{nomina_id}")
async def cambiar_estado_nomina(nomina_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


@router.post("/api/finanzas/nomina/marcar-pagado/{nomina_id}")
async def marcar_pagado(nomina_id: int, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


@router.get("/api/finanzas/nomina/{nomina_id}/desprendible")
async def get_desprendible(nomina_id: int, user_id: int = Depends(get_current_user_id)):
    # TODO: Return PDF blob
    return {"url": ""}


@router.post("/api/finanzas/nomina/{nomina_id}/enviar-email")
async def enviar_nomina_email(nomina_id: int, data: dict | None = None, user_id: int = Depends(get_current_user_id)):
    return {"success": True}


# ═══════════════════════════════════════════════════════════════
# /api/nominas + /api/nominas-preview
# ═══════════════════════════════════════════════════════════════

@router.post("/api/nominas-preview/preview")
async def preview_nomina(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"items": [], "totales": {"total_sueldos": 0, "total_bonos": 0, "total_deducciones": 0, "total_neto": 0}}


@router.get("/api/nominas-preview/{nomina_id}/export")
async def export_nomina(
    nomina_id: int,
    format: str = Query("pdf"),
):
    # TODO: Return file blob
    return {"url": ""}


@router.post("/api/nominas")
async def create_nomina(data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": 0}


@router.get("/api/nominas/{nomina_id}")
async def get_nomina_detail(nomina_id: int, user_id: int = Depends(get_current_user_id)):
    return {"id": nomina_id}


@router.post("/api/nominas/{nomina_id}/procesar")
async def procesar_nomina(nomina_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": nomina_id}


@router.patch("/api/nominas/{nomina_id}/estado")
async def update_nomina_estado_v2(nomina_id: int, data: dict, user_id: int = Depends(get_current_user_id)):
    return {"id": nomina_id}


@router.delete("/api/nominas/{nomina_id}")
async def delete_nomina(nomina_id: int, user_id: int = Depends(get_current_user_id)):
    return {"success": True, "message": "Nómina eliminada correctamente"}

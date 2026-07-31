"""OKRs service — HTTP routes (C-02)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    require_admin,
    require_manager,
)
from services.okrs.repository import OkrRepository
from services.okrs.schemas import (
    CheckinIn,
    KeyResultIn,
    KeyResultOut,
    KeyResultUpdate,
    OkrDetail,
    OkrIn,
    OkrOut,
    OkrTreeNode,
    OkrUpdate,
    WhatIfRequest,
    WhatIfResponse,
)
from services.okrs.service import OkrService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("okrs"))) -> OkrService:
    return OkrService(OkrRepository(db))


# ─── OKRs ─────────────────────────────────────────
@router.get("/", response_model=list[OkrOut])
async def list_okrs(
    period: str | None = Query(None),
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_okrs(tenant_id, period)


@router.get("/cascade", response_model=list[OkrTreeNode])
async def cascade(
    period: str | None = Query(None),
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.get_cascade(tenant_id, period)


@router.get("/{okr_id}", response_model=OkrDetail)
async def get_okr(
    okr_id: int,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    detail = await service.get_okr_detail(tenant_id, okr_id)
    if not detail:
        raise HTTPException(status_code=404, detail="OKR no encontrado")
    return detail


@router.post("/", response_model=OkrDetail, dependencies=[Depends(require_manager)])
async def create_okr(
    payload: OkrIn,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.create_okr(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/{okr_id}", response_model=OkrDetail, dependencies=[Depends(require_manager)])
async def update_okr(
    okr_id: int,
    payload: OkrUpdate,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    detail = await service.update_okr(tenant_id, okr_id, payload)
    if not detail:
        raise HTTPException(status_code=404, detail="OKR no encontrado")
    return detail


@router.delete("/{okr_id}", dependencies=[Depends(require_admin)])
async def delete_okr(
    okr_id: int,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_okr(tenant_id, okr_id)
    if not ok:
        raise HTTPException(status_code=404, detail="OKR no encontrado")
    return {"ok": True}


# ─── Key Results ─────────────────────────────────────────
@router.post(
    "/{okr_id}/key-results", response_model=KeyResultOut, dependencies=[Depends(require_manager)]
)
async def add_kr(
    okr_id: int,
    payload: KeyResultIn,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.add_kr(tenant_id, okr_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put(
    "/key-results/{kr_id}", response_model=KeyResultOut, dependencies=[Depends(require_manager)]
)
async def update_kr(
    kr_id: int,
    payload: KeyResultUpdate,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    out = await service.update_kr(tenant_id, kr_id, payload)
    if not out:
        raise HTTPException(status_code=404, detail="Key Result no encontrado")
    return out


@router.delete("/key-results/{kr_id}", dependencies=[Depends(require_manager)])
async def delete_kr(
    kr_id: int,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_kr(tenant_id, kr_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key Result no encontrado")
    return {"ok": True}


# ─── What-if (AI-07) ─────────────────────────────────────────
@router.post("/whatif", response_model=WhatIfResponse)
async def whatif(
    payload: WhatIfRequest,
    period: str | None = Query(None),
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Simula el efecto de cambios en KRs sin persistir nada."""
    return await service.whatif(tenant_id, period, payload)


# ─── Check-ins ─────────────────────────────────────────
@router.post("/checkin", response_model=KeyResultOut)
async def checkin(
    payload: CheckinIn,
    service: OkrService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.checkin(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ─── Internal trigger (KPIs → OKRs) ─────────────────────────────────────────
# El service de KPIs llama acá vía HTTP cuando se ingesta una medición.
@router.post("/internal/kpi-checkin")
async def kpi_checkin(
    tenant_id: int = Query(...),
    kpi_id: int = Query(...),
    value: float = Query(...),
    service: OkrService = Depends(get_service),
):
    updated = await service.auto_checkin_from_kpi(tenant_id, kpi_id, value)
    return {"updated_krs": updated}

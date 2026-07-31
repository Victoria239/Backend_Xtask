"""ATS service — HTTP routes (H-03)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_admin, require_manager,
)
from services.ats.repository import AtsRepository
from services.ats.schemas import (
    ApplicationEventOut, ApplicationIn, ApplicationOut, CandidateIn, CandidateOut,
    KanbanView, MoveStage, PipelineDetail, PipelineIn, PipelineSummary, PipelineUpdate,
)
from services.ats.service import AtsService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("ats"))) -> AtsService:
    return AtsService(AtsRepository(db))


# ─── Pipelines ────────────────────────────────────────
@router.get("/pipelines", response_model=list[PipelineSummary])
async def list_pipelines(
    status: str | None = Query(None),
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_pipelines(tenant_id, status)


@router.get("/pipelines/{pipeline_id}", response_model=PipelineDetail)
async def get_pipeline(
    pipeline_id: int,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.get_pipeline_detail(tenant_id, pipeline_id)
    if not d:
        raise HTTPException(status_code=404, detail="Pipeline no encontrado")
    return d


@router.post(
    "/pipelines", response_model=PipelineDetail, dependencies=[Depends(require_manager)]
)
async def create_pipeline(
    payload: PipelineIn,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.create_pipeline(tenant_id, payload)


@router.put(
    "/pipelines/{pipeline_id}", response_model=PipelineDetail, dependencies=[Depends(require_manager)]
)
async def update_pipeline(
    pipeline_id: int, payload: PipelineUpdate,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    d = await service.update_pipeline(tenant_id, pipeline_id, payload)
    if not d:
        raise HTTPException(status_code=404, detail="Pipeline no encontrado")
    return d


@router.delete(
    "/pipelines/{pipeline_id}", dependencies=[Depends(require_admin)]
)
async def delete_pipeline(
    pipeline_id: int,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    ok = await service.delete_pipeline(tenant_id, pipeline_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Pipeline no encontrado")
    return {"ok": True}


# ─── Kanban ─────────────────────────────────────────
@router.get("/pipelines/{pipeline_id}/kanban", response_model=KanbanView)
async def kanban(
    pipeline_id: int,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.kanban(tenant_id, pipeline_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ─── Candidates ────────────────────────────────────────
@router.get("/candidates", response_model=list[CandidateOut])
async def list_candidates(
    search: str | None = Query(None),
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_candidates(tenant_id, search)


@router.post("/candidates", response_model=CandidateOut, dependencies=[Depends(require_manager)])
async def create_candidate(
    payload: CandidateIn,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.create_candidate(tenant_id, payload)


@router.put(
    "/candidates/{candidate_id}", response_model=CandidateOut, dependencies=[Depends(require_manager)]
)
async def update_candidate(
    candidate_id: int, payload: CandidateIn,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    out = await service.update_candidate(tenant_id, candidate_id, payload)
    if not out:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    return out


# ─── Applications ─────────────────────────────────────
@router.post(
    "/pipelines/{pipeline_id}/applications", response_model=ApplicationOut,
    dependencies=[Depends(require_manager)],
)
async def add_application(
    pipeline_id: int, payload: ApplicationIn,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.add_application(tenant_id, pipeline_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/applications/{app_id}/move", response_model=ApplicationOut,
    dependencies=[Depends(require_manager)],
)
async def move_application(
    app_id: int, payload: MoveStage,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.move_application(tenant_id, app_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/applications/{app_id}/events", response_model=list[ApplicationEventOut])
async def list_application_events(
    app_id: int,
    service: AtsService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.list_events(tenant_id, app_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

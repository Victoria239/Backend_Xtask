"""Projects service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id
from services.projects.repository import ProjectRepository
from services.projects.service import ProjectService
from services.projects.schemas import ProjectCreate, ProjectUpdate, ProjectOut, ProjectStatusUpdate

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(ProjectRepository(db))


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    estado: str | None = Query(None),
    busqueda: str | None = Query(None),
    departamentoId: int | None = Query(None),
    responsableId: int | None = Query(None),
    pageSize: int | None = Query(None),
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if estado:
        filters["estado"] = estado
    if busqueda:
        filters["busqueda"] = busqueda
    return await service.list_projects(filters if filters else None)


@router.get("/indicadores")
async def get_indicators(
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_indicators()


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_project(project_id)


@router.post("", response_model=ProjectOut)
async def create_project(
    data: ProjectCreate,
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_project(data)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_project(project_id, data)


@router.patch("/{project_id}/estado", response_model=ProjectOut)
async def change_status(
    project_id: int,
    data: ProjectStatusUpdate,
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.change_status(project_id, data.estado)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    service: ProjectService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_project(project_id)

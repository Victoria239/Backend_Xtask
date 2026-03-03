"""Skills service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.dependencies import get_current_user_id, require_admin, require_manager
from services.skills.repository import SkillRepository
from services.skills.service import SkillService
from services.skills.schemas import SkillCreate, SkillUpdate, SkillOut

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> SkillService:
    return SkillService(SkillRepository(db))


@router.get("")
async def list_skills(
    employee_id: int | None = Query(None),
    category: str | None = Query(None),
    level: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    service: SkillService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if employee_id:
        filters["employee_id"] = employee_id
    if category:
        filters["category"] = category
    if level:
        filters["level"] = level
    return await service.list_skills_paginated(filters if filters else None, page, page_size)


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(
    skill_id: int,
    service: SkillService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_skill(skill_id)


@router.post("", response_model=SkillOut, dependencies=[Depends(require_manager)])
async def create_skill(
    data: SkillCreate,
    service: SkillService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_skill(data)


@router.patch("/{skill_id}", response_model=SkillOut, dependencies=[Depends(require_manager)])
async def update_skill(
    skill_id: int,
    data: SkillUpdate,
    service: SkillService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_skill(skill_id, data)


@router.delete("/{skill_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_skill(
    skill_id: int,
    service: SkillService = Depends(get_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_skill(skill_id)

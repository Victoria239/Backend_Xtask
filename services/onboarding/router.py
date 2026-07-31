"""Onboarding service - HTTP routes (H-02)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    require_admin,
    require_manager,
)
from services.onboarding.repository import OnboardingRepository
from services.onboarding.schemas import (
    AssignmentOut,
    AssignmentSummary,
    AssignRequest,
    StepUpdate,
    TemplateIn,
    TemplateOut,
)
from services.onboarding.service import OnboardingService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("onboarding"))) -> OnboardingService:
    return OnboardingService(OnboardingRepository(db))


# ─── Templates ────────────────────────────────────────────────
@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_templates(tenant_id)


@router.post("/templates", response_model=TemplateOut, dependencies=[Depends(require_manager)])
async def create_template(
    payload: TemplateIn,
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.create_template(tenant_id, payload)


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
async def delete_template(
    template_id: int,
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    await service.delete_template(tenant_id, template_id)


# ─── Assignments ──────────────────────────────────────────────
@router.post(
    "/assign",
    response_model=AssignmentOut,
    dependencies=[Depends(require_manager)],
)
async def assign(
    payload: AssignRequest,
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.assign(tenant_id, payload.employee_id, payload.template_id)


@router.get("/employee/{employee_id}", response_model=AssignmentOut | None)
async def get_employee_assignment(
    employee_id: int,
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.get_for_employee(tenant_id, employee_id)


@router.patch(
    "/steps/{step_id}",
    response_model=AssignmentOut,
)
async def update_step(
    step_id: int,
    payload: StepUpdate,
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    step = await service.update_step(tenant_id, step_id, payload.status, user_id)
    # Devolvemos el assignment completo para que el frontend pueda re-render
    assignment = await service.repo.get_assignment(tenant_id, step.assignment_id)
    return assignment


@router.get("/summary", response_model=list[AssignmentSummary])
async def admin_summary(
    service: OnboardingService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.admin_summary(tenant_id)

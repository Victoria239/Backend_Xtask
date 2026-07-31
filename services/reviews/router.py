"""Reviews 360° — HTTP routes (H-05)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id, get_current_user_id, require_manager,
)
from services.reviews.models import ReviewAssignment, ReviewCycle
from services.reviews.questions import QUESTIONS
from services.reviews.schemas import (
    AssignmentSummary, CycleCreate, CycleOut, QuestionOut, SubmitRequest, SummaryOut,
)
from services.reviews.service import ReviewsService

router = APIRouter()


def get_svc(db: AsyncSession = Depends(get_service_db("reviews"))) -> ReviewsService:
    return ReviewsService(db)


async def _employee_id_for_user(db: AsyncSession, tenant_id: int, user_id: int) -> int:
    """Resolve current user → employee_id in tenant."""
    eid = (await db.execute(text(
        "SELECT id FROM svc_employees.employees WHERE tenant_id = :t AND user_id = :u"
    ), {"t": tenant_id, "u": user_id})).scalar()
    if not eid:
        raise HTTPException(status_code=404, detail="No tenés perfil de empleado en este tenant")
    return int(eid)


# ─── Catálogo de preguntas ───────────────────────────────────
@router.get("/questions", response_model=list[QuestionOut])
async def list_questions(
    _user_id: int = Depends(get_current_user_id),  # solo usuarios autenticados
):
    return [QuestionOut(code=q.code, category=q.category, text=q.text) for q in QUESTIONS]


# ─── Cycles (admin) ──────────────────────────────────────────
@router.post("/cycles", response_model=CycleOut, dependencies=[Depends(require_manager)])
async def create_cycle(
    payload: CycleCreate,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    c = await svc.create_cycle(tenant_id, payload.name, payload.period, payload.deadline, user_id)
    await svc.db.commit()
    cycles = await svc.list_cycles(tenant_id)
    return next(x for x in cycles if x["id"] == c.id)


@router.get("/cycles", response_model=list[CycleOut])
async def list_cycles(
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await svc.list_cycles(tenant_id)


@router.post("/cycles/{cycle_id}/assign", dependencies=[Depends(require_manager)])
async def assign_cycle(
    cycle_id: int,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        n = await svc.auto_assign(tenant_id, cycle_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await svc.db.commit()
    return {"cycle_id": cycle_id, "assignments_created": n}


@router.post("/cycles/{cycle_id}/close", dependencies=[Depends(require_manager)])
async def close_cycle(
    cycle_id: int,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        res = await svc.close_cycle(tenant_id, cycle_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await svc.db.commit()
    return res


# ─── Reviewer perspective ────────────────────────────────────
@router.get("/my-pending", response_model=list[AssignmentSummary])
async def my_pending(
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    eid = await _employee_id_for_user(svc.db, tenant_id, user_id)
    return await svc.list_pending(tenant_id, eid)


@router.get("/assignments/{assignment_id}/form")
async def get_form(
    assignment_id: int,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    eid = await _employee_id_for_user(svc.db, tenant_id, user_id)
    try:
        return await svc.get_form(tenant_id, assignment_id, eid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/assignments/{assignment_id}/submit")
async def submit(
    assignment_id: int,
    payload: SubmitRequest,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    eid = await _employee_id_for_user(svc.db, tenant_id, user_id)
    try:
        res = await svc.submit(tenant_id, assignment_id, eid,
                                [r.model_dump() for r in payload.responses])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await svc.db.commit()
    return res


# ─── Resultados (after close) ────────────────────────────────
@router.get("/my-summary", response_model=list[SummaryOut])
async def my_summary(
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    eid = await _employee_id_for_user(svc.db, tenant_id, user_id)
    return await svc.get_employee_summary(tenant_id, eid)


@router.get("/employee/{employee_id}/summary", response_model=list[SummaryOut], dependencies=[Depends(require_manager)])
async def employee_summary(
    employee_id: int,
    svc: ReviewsService = Depends(get_svc),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await svc.get_employee_summary(tenant_id, employee_id)

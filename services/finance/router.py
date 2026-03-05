"""Finance service - API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_user_id, require_admin, require_manager
from services.finance.repository import BudgetRepository, InvoiceRepository
from services.finance.service import BudgetService, InvoiceService
from services.finance.schemas import (
    BudgetCreate, BudgetUpdate, BudgetOut, ExpenseRegister,
    InvoiceCreate, InvoiceUpdate, InvoiceOut, InvoiceStatusUpdate,
)

router = APIRouter()


def get_budget_service(db: AsyncSession = Depends(get_service_db("finance"))) -> BudgetService:
    return BudgetService(BudgetRepository(db))


def get_invoice_service(db: AsyncSession = Depends(get_service_db("finance"))) -> InvoiceService:
    return InvoiceService(InvoiceRepository(db))


# ═══════════════════════════════════════════════════════════════
# PRESUPUESTOS / BUDGETS
# ═══════════════════════════════════════════════════════════════

@router.get("/presupuestos")
async def list_budgets(
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if status:
        filters["status"] = status
    if project_id:
        filters["project_id"] = project_id
    return await service.list_budgets_paginated(filters if filters else None, page, page_size)


@router.get("/presupuestos/{budget_id}", response_model=BudgetOut)
async def get_budget(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_budget(budget_id)


@router.post("/presupuestos", response_model=BudgetOut, dependencies=[Depends(require_manager)])
async def create_budget(
    data: BudgetCreate,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_budget(data)


@router.patch("/presupuestos/{budget_id}", response_model=BudgetOut, dependencies=[Depends(require_manager)])
async def update_budget(
    budget_id: int,
    data: BudgetUpdate,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_budget(budget_id, data)


@router.delete("/presupuestos/{budget_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_budget(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_budget(budget_id)


@router.get("/presupuestos/{budget_id}/ejecucion")
async def get_budget_execution(
    budget_id: int,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_execution(budget_id)


@router.post("/presupuestos/{budget_id}/gastos", response_model=BudgetOut, dependencies=[Depends(require_manager)])
async def register_expense(
    budget_id: int,
    data: ExpenseRegister,
    service: BudgetService = Depends(get_budget_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.register_expense(budget_id, data)


# ═══════════════════════════════════════════════════════════════
# FACTURAS / INVOICES
# ═══════════════════════════════════════════════════════════════

@router.get("/facturas")
async def list_invoices(
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    client: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    filters = {}
    if status:
        filters["status"] = status
    if project_id:
        filters["project_id"] = project_id
    if client:
        filters["client"] = client
    return await service.list_invoices_paginated(filters if filters else None, page, page_size)


@router.get("/facturas/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: int,
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.get_invoice(invoice_id)


@router.post("/facturas", response_model=InvoiceOut, dependencies=[Depends(require_manager)])
async def create_invoice(
    data: InvoiceCreate,
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_invoice(data)


@router.patch("/facturas/{invoice_id}", response_model=InvoiceOut, dependencies=[Depends(require_manager)])
async def update_invoice(
    invoice_id: int,
    data: InvoiceUpdate,
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_invoice(invoice_id, data)


@router.patch("/facturas/{invoice_id}/estado", response_model=InvoiceOut, dependencies=[Depends(require_manager)])
async def update_invoice_status(
    invoice_id: int,
    data: InvoiceStatusUpdate,
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    return await service.update_status(invoice_id, data.status)


@router.delete("/facturas/{invoice_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_invoice(
    invoice_id: int,
    service: InvoiceService = Depends(get_invoice_service),
    user_id: int = Depends(get_current_user_id),
):
    await service.delete_invoice(invoice_id)

"""Finance service - Business logic."""

from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from services.finance.repository import BudgetRepository, InvoiceRepository
from services.finance.schemas import (
    BudgetCreate, BudgetUpdate, BudgetOut, ExpenseRegister,
    InvoiceCreate, InvoiceUpdate, InvoiceOut,
)


class BudgetService:
    def __init__(self, repo: BudgetRepository):
        self.repo = repo

    async def list_budgets(self, filters: dict | None = None) -> list[BudgetOut]:
        budgets = await self.repo.get_all(filters)
        return [BudgetOut.model_validate(b) for b in budgets]

    async def list_budgets_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return PaginatedResponse.create(
            items=[BudgetOut.model_validate(b) for b in items],
            total=total, page=page, page_size=page_size,
        )

    async def get_budget(self, budget_id: int) -> BudgetOut:
        budget = await self.repo.get_by_id(budget_id)
        if not budget:
            raise NotFoundException("Budget", budget_id)
        return BudgetOut.model_validate(budget)

    async def create_budget(self, data: BudgetCreate) -> BudgetOut:
        budget = await self.repo.create(data.model_dump())
        return BudgetOut.model_validate(budget)

    async def update_budget(self, budget_id: int, data: BudgetUpdate) -> BudgetOut:
        budget = await self.repo.update(budget_id, data.model_dump(exclude_unset=True))
        if not budget:
            raise NotFoundException("Budget", budget_id)
        return BudgetOut.model_validate(budget)

    async def delete_budget(self, budget_id: int) -> None:
        deleted = await self.repo.delete(budget_id)
        if not deleted:
            raise NotFoundException("Budget", budget_id)

    async def register_expense(self, budget_id: int, data: ExpenseRegister) -> BudgetOut:
        budget = await self.repo.register_expense(budget_id, data.amount)
        if not budget:
            raise NotFoundException("Budget", budget_id)
        return BudgetOut.model_validate(budget)

    async def get_execution(self, budget_id: int) -> dict:
        budget = await self.repo.get_by_id(budget_id)
        if not budget:
            raise NotFoundException("Budget", budget_id)
        total = float(budget.total_amount)
        spent = float(budget.spent_amount)
        remaining = total - spent
        percentage = (spent / total * 100) if total > 0 else 0
        return {
            "budget_id": budget.id,
            "total_amount": total,
            "spent_amount": spent,
            "remaining_amount": remaining,
            "execution_percentage": round(percentage, 2),
        }


class InvoiceService:
    def __init__(self, repo: InvoiceRepository):
        self.repo = repo

    async def list_invoices(self, filters: dict | None = None) -> list[InvoiceOut]:
        invoices = await self.repo.get_all(filters)
        return [InvoiceOut.model_validate(i) for i in invoices]

    async def list_invoices_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return PaginatedResponse.create(
            items=[InvoiceOut.model_validate(i) for i in items],
            total=total, page=page, page_size=page_size,
        )

    async def get_invoice(self, invoice_id: int) -> InvoiceOut:
        invoice = await self.repo.get_by_id(invoice_id)
        if not invoice:
            raise NotFoundException("Invoice", invoice_id)
        return InvoiceOut.model_validate(invoice)

    async def create_invoice(self, data: InvoiceCreate) -> InvoiceOut:
        invoice = await self.repo.create(data.model_dump())
        return InvoiceOut.model_validate(invoice)

    async def update_invoice(self, invoice_id: int, data: InvoiceUpdate) -> InvoiceOut:
        invoice = await self.repo.update(invoice_id, data.model_dump(exclude_unset=True))
        if not invoice:
            raise NotFoundException("Invoice", invoice_id)
        return InvoiceOut.model_validate(invoice)

    async def update_status(self, invoice_id: int, status: str) -> InvoiceOut:
        invoice = await self.repo.update_status(invoice_id, status)
        if not invoice:
            raise NotFoundException("Invoice", invoice_id)
        return InvoiceOut.model_validate(invoice)

    async def delete_invoice(self, invoice_id: int) -> None:
        deleted = await self.repo.delete(invoice_id)
        if not deleted:
            raise NotFoundException("Invoice", invoice_id)

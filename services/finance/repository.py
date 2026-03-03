"""Finance service - Database repository."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, desc

from services.finance.models import Budget, Invoice
from shared.repository import BaseRepository


class BudgetRepository(BaseRepository[Budget]):
    model = Budget

    async def register_expense(self, budget_id: int, amount: float) -> Budget | None:
        budget = await self.get_by_id(budget_id)
        if not budget:
            return None
        budget.spent_amount = float(budget.spent_amount) + amount
        await self.db.flush()
        await self.db.refresh(budget)
        return budget


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def get_all(self, filters: dict[str, Any] | None = None, **kwargs) -> list[Invoice]:
        """Override to support ilike search on client name."""
        query = select(Invoice).order_by(desc(Invoice.created_at))
        if filters:
            if filters.get("status"):
                query = query.where(Invoice.status == filters["status"])
            if filters.get("project_id"):
                query = query.where(Invoice.project_id == filters["project_id"])
            if filters.get("client"):
                query = query.where(Invoice.client.ilike(f"%{filters['client']}%"))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_status(self, invoice_id: int, status: str) -> Invoice | None:
        invoice = await self.get_by_id(invoice_id)
        if not invoice:
            return None
        invoice.status = status
        if status == "paid":
            invoice.paid_date = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

"""Finance service - Database repository."""

from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.finance.models import Budget, Invoice


class BudgetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Budget]:
        query = select(Budget).order_by(desc(Budget.created_at))
        if filters:
            if filters.get("status"):
                query = query.where(Budget.status == filters["status"])
            if filters.get("project_id"):
                query = query.where(Budget.project_id == filters["project_id"])
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, budget_id: int) -> Budget | None:
        result = await self.db.execute(select(Budget).where(Budget.id == budget_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Budget:
        budget = Budget(**data)
        self.db.add(budget)
        await self.db.flush()
        await self.db.refresh(budget)
        return budget

    async def update(self, budget_id: int, data: dict) -> Budget | None:
        budget = await self.get_by_id(budget_id)
        if not budget:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(budget, key, value)
        await self.db.flush()
        await self.db.refresh(budget)
        return budget

    async def delete(self, budget_id: int) -> bool:
        budget = await self.get_by_id(budget_id)
        if not budget:
            return False
        await self.db.delete(budget)
        await self.db.flush()
        return True

    async def register_expense(self, budget_id: int, amount: float) -> Budget | None:
        budget = await self.get_by_id(budget_id)
        if not budget:
            return None
        budget.spent_amount = float(budget.spent_amount) + amount
        await self.db.flush()
        await self.db.refresh(budget)
        return budget


class InvoiceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Invoice]:
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

    async def get_by_id(self, invoice_id: int) -> Invoice | None:
        result = await self.db.execute(select(Invoice).where(Invoice.id == invoice_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Invoice:
        invoice = Invoice(**data)
        self.db.add(invoice)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

    async def update(self, invoice_id: int, data: dict) -> Invoice | None:
        invoice = await self.get_by_id(invoice_id)
        if not invoice:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(invoice, key, value)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice

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

    async def delete(self, invoice_id: int) -> bool:
        invoice = await self.get_by_id(invoice_id)
        if not invoice:
            return False
        await self.db.delete(invoice)
        await self.db.flush()
        return True

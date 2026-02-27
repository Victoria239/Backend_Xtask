"""Payroll service - Database repository."""

from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.payroll.models import Payroll


class PayrollRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Payroll]:
        query = select(Payroll).order_by(desc(Payroll.created_at))
        if filters:
            if filters.get("employee_id"):
                query = query.where(Payroll.employee_id == filters["employee_id"])
            if filters.get("period"):
                query = query.where(Payroll.period == filters["period"])
            if filters.get("status"):
                query = query.where(Payroll.status == filters["status"])
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, payroll_id: int) -> Payroll | None:
        result = await self.db.execute(select(Payroll).where(Payroll.id == payroll_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Payroll:
        payroll = Payroll(**data)
        self.db.add(payroll)
        await self.db.flush()
        await self.db.refresh(payroll)
        return payroll

    async def update(self, payroll_id: int, data: dict) -> Payroll | None:
        payroll = await self.get_by_id(payroll_id)
        if not payroll:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(payroll, key, value)
        # Recalculate net salary if salary components changed
        payroll.net_salary = float(payroll.base_salary) + float(payroll.bonuses) - float(payroll.deductions)
        await self.db.flush()
        await self.db.refresh(payroll)
        return payroll

    async def update_status(self, payroll_id: int, status: str) -> Payroll | None:
        payroll = await self.get_by_id(payroll_id)
        if not payroll:
            return None
        payroll.status = status
        if status == "paid":
            payroll.paid_date = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(payroll)
        return payroll

    async def delete(self, payroll_id: int) -> bool:
        payroll = await self.get_by_id(payroll_id)
        if not payroll:
            return False
        await self.db.delete(payroll)
        await self.db.flush()
        return True

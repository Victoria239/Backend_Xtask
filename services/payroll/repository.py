"""Payroll service - Database repository."""

from datetime import datetime, timezone
from typing import Any

from services.payroll.models import Payroll
from shared.repository import BaseRepository


class PayrollRepository(BaseRepository[Payroll]):
    model = Payroll

    async def update(self, entity_id: int, data: dict[str, Any]) -> Payroll | None:
        """Override to recalculate net_salary on update."""
        payroll = await self.get_by_id(entity_id)
        if not payroll:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(payroll, key, value)
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

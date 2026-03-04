"""Payroll service - Database repository."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

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

    async def get_metrics(self, filters: dict[str, Any] | None = None) -> dict:
        """Return payroll metrics using SQL aggregation."""
        base = select(
            func.coalesce(func.sum(Payroll.net_salary), 0).label("total_monthly"),
            func.coalesce(
                func.sum(Payroll.net_salary).filter(Payroll.status == "pending"), 0
            ).label("pending"),
            func.coalesce(
                func.sum(Payroll.net_salary).filter(Payroll.status == "paid"), 0
            ).label("paid"),
            func.count().label("count"),
        ).select_from(Payroll)
        if filters and filters.get("period"):
            base = base.where(Payroll.period == filters["period"])
        result = await self.db.execute(base)
        row = result.one()
        return {
            "totalMensual": float(row.total_monthly),
            "pendientePago": float(row.pending),
            "pagadoMes": float(row.paid),
            "totalNominas": row.count,
        }

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

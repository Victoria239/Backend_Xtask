"""KPIs service - Database repository."""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.kpis.models import Kpi


class KpiRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, filters: dict | None = None) -> list[Kpi]:
        query = select(Kpi).order_by(desc(Kpi.created_at))
        if filters:
            if filters.get("employee_id"):
                query = query.where(Kpi.employee_id == filters["employee_id"])
            if filters.get("period"):
                query = query.where(Kpi.period == filters["period"])
            if filters.get("status"):
                query = query.where(Kpi.status == filters["status"])
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, kpi_id: int) -> Kpi | None:
        result = await self.db.execute(select(Kpi).where(Kpi.id == kpi_id))
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> Kpi:
        kpi = Kpi(**data)
        self.db.add(kpi)
        await self.db.flush()
        await self.db.refresh(kpi)
        return kpi

    async def update(self, kpi_id: int, data: dict) -> Kpi | None:
        kpi = await self.get_by_id(kpi_id)
        if not kpi:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(kpi, key, value)
        await self.db.flush()
        await self.db.refresh(kpi)
        return kpi

    async def delete(self, kpi_id: int) -> bool:
        kpi = await self.get_by_id(kpi_id)
        if not kpi:
            return False
        await self.db.delete(kpi)
        await self.db.flush()
        return True

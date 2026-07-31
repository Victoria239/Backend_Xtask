"""KPIs service - Database repository."""

from sqlalchemy import select

from services.kpis.models import Kpi, KpiMeasurement
from shared.repository import BaseRepository


class KpiRepository(BaseRepository[Kpi]):
    model = Kpi

    async def add_measurement(self, tenant_id: int | None, kpi_id: int, **fields) -> KpiMeasurement:
        m = KpiMeasurement(tenant_id=tenant_id, kpi_id=kpi_id, **fields)
        self.db.add(m)
        await self.db.flush()
        return m

    async def list_measurements(self, kpi_id: int, limit: int = 200) -> list[KpiMeasurement]:
        res = await self.db.execute(
            select(KpiMeasurement)
            .where(KpiMeasurement.kpi_id == kpi_id)
            .order_by(KpiMeasurement.recorded_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def update_actual_from_latest(self, kpi_id: int) -> None:
        res = await self.db.execute(
            select(KpiMeasurement.value)
            .where(KpiMeasurement.kpi_id == kpi_id)
            .order_by(KpiMeasurement.recorded_at.desc(), KpiMeasurement.id.desc())
            .limit(1)
        )
        latest = res.scalar_one_or_none()
        if latest is None:
            return
        kpi = await self.get_by_id(kpi_id)
        if kpi is None:
            return
        kpi.actual_value = latest
        if kpi.target_value and float(latest) >= float(kpi.target_value):
            kpi.status = "achieved"
        else:
            kpi.status = "in_progress"
        await self.db.flush()

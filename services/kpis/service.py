"""KPIs service - Business logic."""

from shared.exceptions import NotFoundException
from services.kpis.repository import KpiRepository
from services.kpis.schemas import KpiCreate, KpiUpdate, KpiOut


class KpiService:
    def __init__(self, repo: KpiRepository):
        self.repo = repo

    async def list_kpis(self, filters: dict | None = None) -> list[KpiOut]:
        kpis = await self.repo.get_all(filters)
        return [KpiOut.model_validate(k) for k in kpis]

    async def get_kpi(self, kpi_id: int) -> KpiOut:
        kpi = await self.repo.get_by_id(kpi_id)
        if not kpi:
            raise NotFoundException("KPI", kpi_id)
        return KpiOut.model_validate(kpi)

    async def create_kpi(self, data: KpiCreate) -> KpiOut:
        kpi = await self.repo.create(data.model_dump())
        return KpiOut.model_validate(kpi)

    async def update_kpi(self, kpi_id: int, data: KpiUpdate) -> KpiOut:
        kpi = await self.repo.update(kpi_id, data.model_dump(exclude_unset=True))
        if not kpi:
            raise NotFoundException("KPI", kpi_id)
        return KpiOut.model_validate(kpi)

    async def evaluate_kpi(self, kpi_id: int, actual_value: float) -> KpiOut:
        kpi = await self.repo.get_by_id(kpi_id)
        if not kpi:
            raise NotFoundException("KPI", kpi_id)
        status = "achieved" if actual_value >= float(kpi.target_value) else "not_achieved"
        updated = await self.repo.update(kpi_id, {"actual_value": actual_value, "status": status})
        return KpiOut.model_validate(updated)

    async def validate_kpi(self, kpi_id: int, validated: bool) -> KpiOut:
        kpi = await self.repo.update(kpi_id, {"validated": validated})
        if not kpi:
            raise NotFoundException("KPI", kpi_id)
        return KpiOut.model_validate(kpi)

    async def delete_kpi(self, kpi_id: int) -> None:
        deleted = await self.repo.delete(kpi_id)
        if not deleted:
            raise NotFoundException("KPI", kpi_id)

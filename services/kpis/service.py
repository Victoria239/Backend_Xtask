"""KPIs service - Business logic."""

from sqlalchemy import text

from shared.builders import ResponseBuilder
from shared.exceptions import NotFoundException
from shared.notifications import emit_notification
from shared.schemas import PaginatedResponse
from services.kpis.repository import KpiRepository
from services.kpis.schemas import (
    KpiCreate,
    KpiMeasurementIn,
    KpiMeasurementIngestResponse,
    KpiMeasurementOut,
    KpiOut,
    KpiUpdate,
)


class KpiService:
    def __init__(self, repo: KpiRepository):
        self.repo = repo

    async def list_kpis_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return (
            ResponseBuilder()
            .with_items(items, KpiOut)
            .with_pagination(total=total, page=page, page_size=page_size)
            .with_filters(filters)
            .build()
        )

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
        old_status = kpi.status
        pct = (actual_value / float(kpi.target_value)) * 100 if kpi.target_value else 0
        # Status semáforo: ≥100 met · ≥80 on-track · ≥50 at-risk · <50 failed
        if pct >= 120:
            status = "exceeded"
        elif pct >= 100:
            status = "met"
        elif pct >= 80:
            status = "on-track"
        elif pct >= 50:
            status = "at-risk"
        else:
            status = "failed"
        updated = await self.repo.update(kpi_id, {"actual_value": actual_value, "status": status})

        # P-04: notif al user del empleado cuando crossing a "at-risk" o "failed"
        if status in ("at-risk", "failed") and status != old_status:
            try:
                row = (await self.repo.db.execute(
                    text("SELECT user_id, tenant_id FROM svc_employees.employees WHERE id = :eid LIMIT 1"),
                    {"eid": kpi.employee_id},
                )).first()
                if row:
                    user_id, tenant_id = int(row[0]) if row[0] else None, int(row[1]) if row[1] else None
                    kind = "warning" if status == "at-risk" else "error"
                    label = "en riesgo" if status == "at-risk" else "no cumplido"
                    await emit_notification(
                        self.repo.db,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        title=f'KPI "{kpi.name}" {label}',
                        body=f"Cumplimiento actual {pct:.0f}% del target {kpi.target_value}. Revisá las acciones para recuperarlo.",
                        kind=kind,
                        category="kpis",
                        action_url="/kpis",
                        meta={"kpi_id": kpi_id, "status": status, "pct": round(pct, 1)},
                    )
            except Exception:  # noqa: BLE001
                pass  # no rompemos la evaluación si la notif falla

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

    # ─── C-01: measurement ingestion ────────────────────────
    async def ingest_measurements(
        self, tenant_id: int | None, measurements: list[KpiMeasurementIn]
    ) -> KpiMeasurementIngestResponse:
        updated: set[int] = set()
        inserted = 0
        for m in measurements:
            kpi = await self.repo.get_by_id(m.kpi_id)
            if not kpi:
                raise NotFoundException("KPI", m.kpi_id)
            payload = m.model_dump(exclude={"kpi_id"})
            # Drop None recorded_at so the server default kicks in
            payload = {k: v for k, v in payload.items() if v is not None}
            await self.repo.add_measurement(tenant_id=tenant_id, kpi_id=m.kpi_id, **payload)
            await self.repo.update_actual_from_latest(m.kpi_id)
            updated.add(m.kpi_id)
            inserted += 1

            # C-02 hook: propagar al servicio de OKRs los KRs que tengan linked_kpi_id
            await _trigger_okr_checkin(tenant_id, m.kpi_id, float(m.value))
        return KpiMeasurementIngestResponse(inserted=inserted, updated_kpis=sorted(updated))

    async def list_measurements(self, kpi_id: int) -> list[KpiMeasurementOut]:
        kpi = await self.repo.get_by_id(kpi_id)
        if not kpi:
            raise NotFoundException("KPI", kpi_id)
        rows = await self.repo.list_measurements(kpi_id)
        return [KpiMeasurementOut.model_validate(r) for r in rows]


# ─── C-02 hook: KPIs → OKRs ───────────────────────────────
import logging as _logging
import httpx as _httpx
from shared.config import get_settings as _get_settings

_okr_logger = _logging.getLogger("kpis.okr_hook")


async def _trigger_okr_checkin(tenant_id: int | None, kpi_id: int, value: float) -> None:
    """Best-effort call al svc OKRs para propagar el check-in. No bloquea si falla."""
    if tenant_id is None:
        return
    try:
        url = f"{_get_settings().OKRS_SERVICE_URL}/api/okrs/internal/kpi-checkin"
        async with _httpx.AsyncClient(timeout=2.0) as client:
            await client.post(url, params={"tenant_id": tenant_id, "kpi_id": kpi_id, "value": value})
    except Exception as e:  # noqa: BLE001
        _okr_logger.warning("okr_trigger_failed", exc_info=e)

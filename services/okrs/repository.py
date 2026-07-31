"""OKRs service — DB repository (C-02)."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.okrs.models import KeyResult, Okr, OkrCheckin


class OkrRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── OKRs ─────────────────────────────────────────
    async def list_okrs(self, tenant_id: int, period: str | None = None) -> list[Okr]:
        stmt = select(Okr).where(Okr.tenant_id == tenant_id)
        if period:
            stmt = stmt.where(Okr.period == period)
        stmt = stmt.order_by(Okr.scope.desc(), Okr.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_okr(self, tenant_id: int, okr_id: int) -> Okr | None:
        stmt = select(Okr).where(Okr.tenant_id == tenant_id, Okr.id == okr_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_okr(self, **kwargs) -> Okr:
        okr = Okr(**kwargs)
        self.db.add(okr)
        await self.db.flush()
        return okr

    async def update_okr(self, okr: Okr, **kwargs) -> Okr:
        for k, v in kwargs.items():
            if v is not None:
                setattr(okr, k, v)
        await self.db.flush()
        return okr

    async def delete_okr(self, okr: Okr) -> None:
        await self.db.delete(okr)
        await self.db.flush()

    async def update_metrics(self, okr_id: int, progress: float, status: str) -> None:
        await self.db.execute(
            text("UPDATE svc_okrs.okrs SET progress = :p, status = :s, updated_at = NOW() WHERE id = :id"),
            {"p": progress, "s": status, "id": okr_id},
        )

    # ─── Key Results ─────────────────────────────────────────
    async def list_krs(self, okr_id: int) -> list[KeyResult]:
        stmt = select(KeyResult).where(KeyResult.okr_id == okr_id).order_by(KeyResult.id.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_kr(self, tenant_id: int, kr_id: int) -> KeyResult | None:
        stmt = select(KeyResult).where(KeyResult.tenant_id == tenant_id, KeyResult.id == kr_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_krs_by_linked_kpi(self, tenant_id: int, kpi_id: int) -> list[KeyResult]:
        stmt = select(KeyResult).where(
            KeyResult.tenant_id == tenant_id, KeyResult.linked_kpi_id == kpi_id
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_kr(self, **kwargs) -> KeyResult:
        kr = KeyResult(**kwargs)
        self.db.add(kr)
        await self.db.flush()
        return kr

    async def update_kr_current(self, kr_id: int, current: float) -> None:
        await self.db.execute(
            text("UPDATE svc_okrs.key_results SET current = :c, updated_at = NOW() WHERE id = :id"),
            {"c": current, "id": kr_id},
        )

    async def update_kr(self, kr: KeyResult, **kwargs) -> KeyResult:
        for k, v in kwargs.items():
            if v is not None:
                setattr(kr, k, v)
        await self.db.flush()
        return kr

    async def delete_kr(self, kr: KeyResult) -> None:
        await self.db.delete(kr)
        await self.db.flush()

    # ─── Check-ins ─────────────────────────────────────────
    async def add_checkin(self, **kwargs) -> OkrCheckin:
        chk = OkrCheckin(**kwargs)
        self.db.add(chk)
        await self.db.flush()
        return chk

    async def list_checkins(self, kr_id: int, limit: int = 20) -> list[OkrCheckin]:
        stmt = (
            select(OkrCheckin)
            .where(OkrCheckin.kr_id == kr_id)
            .order_by(OkrCheckin.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

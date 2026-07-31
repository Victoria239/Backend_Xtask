"""Payouts service — DB repository (C-04)."""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.payouts.models import Payout, PayoutRun


class PayoutsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_runs(self, tenant_id: int, status: str | None = None) -> list[PayoutRun]:
        stmt = select(PayoutRun).where(PayoutRun.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(PayoutRun.status == status)
        stmt = stmt.order_by(PayoutRun.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_run(self, tenant_id: int, run_id: int) -> PayoutRun | None:
        stmt = select(PayoutRun).where(PayoutRun.tenant_id == tenant_id, PayoutRun.id == run_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_run(self, **kwargs) -> PayoutRun:
        r = PayoutRun(**kwargs)
        self.db.add(r)
        await self.db.flush()
        return r

    async def update_run(self, run: PayoutRun, **kwargs) -> PayoutRun:
        for k, v in kwargs.items():
            if v is not None:
                setattr(run, k, v)
        await self.db.flush()
        return run

    async def delete_run(self, run: PayoutRun) -> None:
        await self.db.delete(run)
        await self.db.flush()

    async def list_payouts_for_run(self, run_id: int) -> list[Payout]:
        stmt = select(Payout).where(Payout.run_id == run_id).order_by(Payout.amount.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_payout(self, tenant_id: int, payout_id: int) -> Payout | None:
        stmt = select(Payout).where(Payout.tenant_id == tenant_id, Payout.id == payout_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_payout(self, **kwargs) -> Payout:
        p = Payout(**kwargs)
        self.db.add(p)
        await self.db.flush()
        return p

    async def update_payout(self, p: Payout, **kwargs) -> Payout:
        for k, v in kwargs.items():
            if v is not None:
                setattr(p, k, v)
        await self.db.flush()
        return p

    # ─── Cross-schema ─────────────────────────────────────────
    async def list_employees(
        self, tenant_id: int, department: str | None = None
    ) -> list[dict]:
        sql = (
            "SELECT id, first_name || ' ' || last_name AS name, department, salary "
            "FROM svc_employees.employees "
            "WHERE tenant_id = :tid AND contract_status = 'active'"
        )
        params: dict[str, object] = {"tid": tenant_id}
        if department:
            sql += " AND department = :dept"
            params["dept"] = department
        sql += " ORDER BY name ASC"
        rows = (await self.db.execute(text(sql), params)).all()
        return [
            {"id": int(r[0]), "name": str(r[1]), "department": r[2], "salary": float(r[3] or 0)}
            for r in rows
        ]

"""Contracts service — DB repository (E-02)."""

from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.contracts.models import Contract, ContractEvent


class ContractRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_contracts(
        self,
        tenant_id: int,
        status: str | None = None,
        employee_id: int | None = None,
    ) -> list[Contract]:
        stmt = select(Contract).where(Contract.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Contract.status == status)
        if employee_id:
            stmt = stmt.where(Contract.employee_id == employee_id)
        stmt = stmt.order_by(Contract.expires_on.asc().nulls_last(), Contract.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_contract(self, tenant_id: int, contract_id: int) -> Contract | None:
        stmt = select(Contract).where(Contract.tenant_id == tenant_id, Contract.id == contract_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create(self, **kwargs) -> Contract:
        contract = Contract(**kwargs)
        self.db.add(contract)
        await self.db.flush()
        return contract

    async def update(self, contract: Contract, **kwargs) -> Contract:
        for k, v in kwargs.items():
            if v is not None:
                setattr(contract, k, v)
        await self.db.flush()
        return contract

    async def delete(self, contract: Contract) -> None:
        await self.db.delete(contract)
        await self.db.flush()

    async def add_event(self, **kwargs) -> ContractEvent:
        ev = ContractEvent(**kwargs)
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def list_events(self, contract_id: int) -> list[ContractEvent]:
        stmt = (
            select(ContractEvent)
            .where(ContractEvent.contract_id == contract_id)
            .order_by(ContractEvent.created_at.desc())
            .limit(50)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def find_expiring(self, today: date, max_days_ahead: int = 60) -> list[Contract]:
        """Contratos que expiran entre hoy y +max_days y aún están activos."""
        stmt = (
            select(Contract)
            .where(
                Contract.status.in_(["signed", "review"]),
                Contract.expires_on.is_not(None),
                Contract.expires_on >= today,
            )
            .order_by(Contract.expires_on.asc())
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        cutoff_days = max_days_ahead
        return [c for c in rows if c.expires_on and (c.expires_on - today).days <= cutoff_days]

    async def mark_alert_sent(self, contract_id: int, alert_key: str) -> None:
        """Agrega alert_key al array alerts_sent (idempotente)."""
        await self.db.execute(
            text(
                """
                UPDATE svc_contracts.contracts
                SET alerts_sent = COALESCE(alerts_sent, '[]'::jsonb) || to_jsonb(CAST(:k AS text))
                WHERE id = :id
                  AND NOT (alerts_sent @> to_jsonb(CAST(:k AS text)))
                """
            ),
            {"id": contract_id, "k": alert_key},
        )

    async def get_employee_user(self, tenant_id: int, employee_id: int) -> tuple[int | None, str]:
        """Devuelve (user_id, full_name) o (None, '?') si no existe."""
        row = (
            await self.db.execute(
                text(
                    "SELECT user_id, first_name || ' ' || last_name FROM svc_employees.employees "
                    "WHERE id = :eid AND tenant_id = :tid LIMIT 1"
                ),
                {"eid": employee_id, "tid": tenant_id},
            )
        ).first()
        if not row:
            return None, "?"
        return int(row[0]) if row[0] else None, str(row[1]) if row[1] else "?"

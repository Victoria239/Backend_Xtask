"""Leaves service — DB repository (H-04)."""

from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.leaves.models import Leave, LeaveBalance, LeaveEvent, LeaveType


class LeavesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Types ────────────────────────────────────────
    async def list_types(self, tenant_id: int, active_only: bool = True) -> list[LeaveType]:
        stmt = select(LeaveType).where(LeaveType.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(LeaveType.active.is_(True))
        stmt = stmt.order_by(LeaveType.name.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_type(self, tenant_id: int, type_id: int) -> LeaveType | None:
        stmt = select(LeaveType).where(
            LeaveType.tenant_id == tenant_id, LeaveType.id == type_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_type(self, **kwargs) -> LeaveType:
        lt = LeaveType(**kwargs)
        self.db.add(lt)
        await self.db.flush()
        return lt

    async def update_type(self, lt: LeaveType, **kwargs) -> LeaveType:
        for k, v in kwargs.items():
            if v is not None:
                setattr(lt, k, v)
        await self.db.flush()
        return lt

    # ─── Leaves ────────────────────────────────────────
    async def list_leaves(
        self,
        tenant_id: int,
        employee_id: int | None = None,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Leave]:
        stmt = select(Leave).where(Leave.tenant_id == tenant_id)
        if employee_id:
            stmt = stmt.where(Leave.employee_id == employee_id)
        if status:
            stmt = stmt.where(Leave.status == status)
        if date_from:
            stmt = stmt.where(Leave.end_date >= date_from)
        if date_to:
            stmt = stmt.where(Leave.start_date <= date_to)
        stmt = stmt.order_by(Leave.start_date.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_leave(self, tenant_id: int, leave_id: int) -> Leave | None:
        stmt = select(Leave).where(Leave.tenant_id == tenant_id, Leave.id == leave_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_leave(self, **kwargs) -> Leave:
        leave = Leave(**kwargs)
        self.db.add(leave)
        await self.db.flush()
        return leave

    async def update_leave(self, leave: Leave, **kwargs) -> Leave:
        for k, v in kwargs.items():
            if v is not None:
                setattr(leave, k, v)
        await self.db.flush()
        return leave

    async def delete_leave(self, leave: Leave) -> None:
        await self.db.delete(leave)
        await self.db.flush()

    async def add_event(self, **kwargs) -> LeaveEvent:
        ev = LeaveEvent(**kwargs)
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def list_events(self, leave_id: int) -> list[LeaveEvent]:
        stmt = (
            select(LeaveEvent)
            .where(LeaveEvent.leave_id == leave_id)
            .order_by(LeaveEvent.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    # ─── Balances ────────────────────────────────────────
    async def get_balance(
        self, tenant_id: int, employee_id: int, type_id: int, year: int
    ) -> LeaveBalance | None:
        stmt = select(LeaveBalance).where(
            LeaveBalance.tenant_id == tenant_id,
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.type_id == type_id,
            LeaveBalance.year == year,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_balances_for_employee(
        self, tenant_id: int, employee_id: int, year: int
    ) -> list[LeaveBalance]:
        stmt = select(LeaveBalance).where(
            LeaveBalance.tenant_id == tenant_id,
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def upsert_balance(
        self, *, tenant_id: int, employee_id: int, type_id: int, year: int, **fields
    ) -> LeaveBalance:
        existing = await self.get_balance(tenant_id, employee_id, type_id, year)
        if existing:
            for k, v in fields.items():
                if v is not None:
                    setattr(existing, k, v)
            await self.db.flush()
            return existing
        bal = LeaveBalance(
            tenant_id=tenant_id, employee_id=employee_id, type_id=type_id, year=year, **fields
        )
        self.db.add(bal)
        await self.db.flush()
        return bal

    # ─── Helpers cross-schema ─────────────────────────
    async def get_employee_user(self, tenant_id: int, employee_id: int) -> tuple[int | None, str]:
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

    async def get_employee_manager_user(self, tenant_id: int, employee_id: int) -> int | None:
        """Devuelve el user_id del manager del empleado, o None si no tiene."""
        row = (
            await self.db.execute(
                text(
                    """
                    SELECT m.user_id
                    FROM svc_employees.employees e
                    LEFT JOIN svc_employees.employees m ON m.id = e.manager_id AND m.tenant_id = e.tenant_id
                    WHERE e.id = :eid AND e.tenant_id = :tid LIMIT 1
                    """
                ),
                {"eid": employee_id, "tid": tenant_id},
            )
        ).first()
        if not row or not row[0]:
            return None
        return int(row[0])

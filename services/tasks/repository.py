"""Tasks service — DB repository (Tablero de Actividades)."""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.tasks.models import Activity


class TasksRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_activities(
        self,
        tenant_id: int,
        status: str | None = None,
        assignee_employee_id: int | None = None,
    ) -> list[Activity]:
        stmt = select(Activity).where(Activity.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Activity.status == status)
        if assignee_employee_id is not None:
            stmt = stmt.where(Activity.assignee_employee_id == assignee_employee_id)
        stmt = stmt.order_by(Activity.position.asc(), Activity.created_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_activity(self, tenant_id: int, activity_id: int) -> Activity | None:
        stmt = select(Activity).where(
            Activity.tenant_id == tenant_id, Activity.id == activity_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def next_position(self, tenant_id: int, status: str) -> int:
        stmt = select(func.coalesce(func.max(Activity.position), 0)).where(
            Activity.tenant_id == tenant_id, Activity.status == status
        )
        current = (await self.db.execute(stmt)).scalar_one()
        return int(current) + 10

    async def create_activity(self, **kwargs) -> Activity:
        a = Activity(**kwargs)
        self.db.add(a)
        await self.db.flush()
        await self.db.refresh(a)
        return a

    async def update_activity(self, a: Activity, **kwargs) -> Activity:
        for k, v in kwargs.items():
            setattr(a, k, v)
        await self.db.flush()
        # Recargar columnas con onupdate server-side (updated_at) dentro del contexto
        # async; si no, Pydantic lanza MissingGreenlet al serializarlas.
        await self.db.refresh(a)
        return a

    async def delete_activity(self, a: Activity) -> None:
        await self.db.delete(a)
        await self.db.flush()

    async def reconcile(self, tenant_id: int) -> int:
        """Auto-transición perezosa según fechas programadas. Idempotente.

        - pendiente + start_at <= now → en_curso (+ started_at si faltaba)
        - status != finalizada + due_at <= now → finalizada (+ completed_at)

        Devuelve el número de filas afectadas (aprox., para logging).
        """
        now = datetime.now(timezone.utc)
        affected = 0

        # 1) Arranque automático: pendiente cuya fecha de inicio ya llegó.
        res_start = await self.db.execute(
            update(Activity)
            .where(
                Activity.tenant_id == tenant_id,
                Activity.status == "pendiente",
                Activity.start_at.is_not(None),
                Activity.start_at <= now,
            )
            .values(
                status="en_curso",
                started_at=func.coalesce(Activity.started_at, now),
                position=0,
            )
        )
        affected += res_start.rowcount or 0

        # 2) Cierre automático: cualquier no-finalizada cuya fecha de fin ya pasó.
        res_due = await self.db.execute(
            update(Activity)
            .where(
                Activity.tenant_id == tenant_id,
                Activity.status != "finalizada",
                Activity.due_at.is_not(None),
                Activity.due_at <= now,
            )
            .values(
                status="finalizada",
                started_at=func.coalesce(Activity.started_at, now),
                completed_at=func.coalesce(Activity.completed_at, now),
                position=0,
            )
        )
        affected += res_due.rowcount or 0

        if affected:
            await self.db.flush()
        return affected

    async def counts_by(self, tenant_id: int, column) -> dict[str, int]:
        stmt = (
            select(column, func.count(Activity.id))
            .where(Activity.tenant_id == tenant_id)
            .group_by(column)
        )
        rows = (await self.db.execute(stmt)).all()
        return {str(k): int(v) for k, v in rows}

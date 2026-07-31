"""Tasks service — business logic (Tablero de Actividades)."""

import logging
from datetime import datetime, timezone

from services.tasks.models import Activity
from services.tasks.repository import TasksRepository
from services.tasks.schemas import (
    ActivityIn, ActivityOut, ActivityUpdate, BoardColumn, BoardMetrics, BoardView,
    MoveActivity, PRIORITIES, STATUSES,
)

logger = logging.getLogger(__name__)

COLUMN_LABELS = {
    "pendiente": "Pendiente",
    "en_curso": "En curso",
    "finalizada": "Finalizada",
}


class TasksService:
    def __init__(self, repo: TasksRepository):
        self.repo = repo

    # ─── Board / list ────────────────────────────────────────
    async def board(self, tenant_id: int) -> BoardView:
        """Tablero de 3 columnas. Ejecuta la auto-transición antes de leer."""
        await self.repo.reconcile(tenant_id)
        activities = await self.repo.list_activities(tenant_id)
        columns = []
        for status in STATUSES:
            cards = [
                ActivityOut.model_validate(a) for a in activities if a.status == status
            ]
            columns.append(
                BoardColumn(status=status, label=COLUMN_LABELS[status], cards=cards)
            )
        return BoardView(columns=columns)

    async def list_activities(
        self,
        tenant_id: int,
        status: str | None = None,
        assignee_employee_id: int | None = None,
    ) -> list[ActivityOut]:
        await self.repo.reconcile(tenant_id)
        items = await self.repo.list_activities(tenant_id, status, assignee_employee_id)
        return [ActivityOut.model_validate(a) for a in items]

    async def get_activity(self, tenant_id: int, activity_id: int) -> ActivityOut | None:
        a = await self.repo.get_activity(tenant_id, activity_id)
        return ActivityOut.model_validate(a) if a else None

    # ─── CRUD ────────────────────────────────────────
    async def create_activity(
        self, tenant_id: int, user_id: int | None, payload: ActivityIn
    ) -> ActivityOut:
        data = payload.model_dump()
        status = data.get("status") or "pendiente"
        if status not in STATUSES:
            raise ValueError(f"Estado inválido: {status}")
        if data.get("priority") not in PRIORITIES:
            raise ValueError(f"Prioridad inválida: {data.get('priority')}")

        data["status"] = status
        data["tenant_id"] = tenant_id
        data["created_by"] = user_id
        data["position"] = await self.repo.next_position(tenant_id, status)

        # Sellos coherentes con el estado inicial elegido manualmente.
        now = datetime.now(timezone.utc)
        if status == "en_curso":
            data["started_at"] = now
        elif status == "finalizada":
            data["started_at"] = now
            data["completed_at"] = now

        a = await self.repo.create_activity(**data)
        # reconcile por si la actividad nació con fechas ya vencidas.
        await self.repo.reconcile(tenant_id)
        refreshed = await self.repo.get_activity(tenant_id, a.id)
        return ActivityOut.model_validate(refreshed or a)

    async def update_activity(
        self, tenant_id: int, activity_id: int, payload: ActivityUpdate
    ) -> ActivityOut | None:
        a = await self.repo.get_activity(tenant_id, activity_id)
        if not a:
            return None
        changes = payload.model_dump(exclude_unset=True)

        if "status" in changes:
            if changes["status"] not in STATUSES:
                raise ValueError(f"Estado inválido: {changes['status']}")
            self._apply_status_stamps(a, changes, changes["status"])
        if "priority" in changes and changes["priority"] not in PRIORITIES:
            raise ValueError(f"Prioridad inválida: {changes['priority']}")

        await self.repo.update_activity(a, **changes)
        await self.repo.reconcile(tenant_id)
        refreshed = await self.repo.get_activity(tenant_id, activity_id)
        return ActivityOut.model_validate(refreshed or a)

    async def move_activity(
        self, tenant_id: int, activity_id: int, payload: MoveActivity
    ) -> ActivityOut | None:
        """Cambio manual de estado (drag entre columnas)."""
        if payload.to_status not in STATUSES:
            raise ValueError(f"Estado inválido: {payload.to_status}")
        a = await self.repo.get_activity(tenant_id, activity_id)
        if not a:
            return None

        changes: dict = {"status": payload.to_status}
        self._apply_status_stamps(a, changes, payload.to_status)
        changes["position"] = (
            payload.position
            if payload.position is not None
            else await self.repo.next_position(tenant_id, payload.to_status)
        )
        await self.repo.update_activity(a, **changes)
        return ActivityOut.model_validate(a)

    def _apply_status_stamps(self, a: Activity, changes: dict, new_status: str) -> None:
        """Fija started_at/completed_at al transicionar manualmente, sin pisar sellos previos."""
        now = datetime.now(timezone.utc)
        if new_status == "en_curso":
            if a.started_at is None:
                changes["started_at"] = now
            changes["completed_at"] = None
        elif new_status == "finalizada":
            if a.started_at is None:
                changes["started_at"] = now
            if a.completed_at is None:
                changes["completed_at"] = now
        elif new_status == "pendiente":
            # Reabrir: limpiar sellos para que el ciclo pueda repetirse.
            changes["started_at"] = None
            changes["completed_at"] = None

    async def delete_activity(self, tenant_id: int, activity_id: int) -> bool:
        a = await self.repo.get_activity(tenant_id, activity_id)
        if not a:
            return False
        await self.repo.delete_activity(a)
        return True

    # ─── Métricas ────────────────────────────────────────
    async def metrics(self, tenant_id: int) -> BoardMetrics:
        await self.repo.reconcile(tenant_id)
        by_status = await self.repo.counts_by(tenant_id, Activity.status)
        by_priority = await self.repo.counts_by(tenant_id, Activity.priority)
        return BoardMetrics(
            total=sum(by_status.values()),
            by_status={s: by_status.get(s, 0) for s in STATUSES},
            by_priority={p: by_priority.get(p, 0) for p in PRIORITIES},
            overdue=0,
        )

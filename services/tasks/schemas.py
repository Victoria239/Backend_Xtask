"""Tasks service — Pydantic schemas (Tablero de Actividades)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

STATUSES = ("pendiente", "en_curso", "finalizada")
PRIORITIES = ("baja", "media", "alta")


# ─── Activities ────────────────────────────────────────
class ActivityIn(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    status: str = "pendiente"
    priority: str = "media"
    assignee_employee_id: int | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None


class ActivityUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_employee_id: int | None = None
    start_at: datetime | None = None
    due_at: datetime | None = None


class MoveActivity(BaseModel):
    """Cambio manual de estado (drag entre columnas)."""

    to_status: str
    position: int | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    status: str
    priority: str
    assignee_employee_id: int | None
    position: int
    start_at: datetime | None
    due_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ─── Board / Kanban ────────────────────────────────────────
class BoardColumn(BaseModel):
    status: str
    label: str
    cards: list[ActivityOut] = Field(default_factory=list)


class BoardView(BaseModel):
    columns: list[BoardColumn] = Field(default_factory=list)


# ─── Métricas ────────────────────────────────────────
class BoardMetrics(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    overdue: int  # con due_at vencido y sin finalizar (no debería pasar tras reconcile)

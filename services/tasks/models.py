"""Tasks service — Tablero de Actividades (backlog + Kanban tipo Jira/Azure DevOps).

Modelo:
- Activity: una actividad/tarea del backlog. Vive en una de tres columnas
  (pendiente · en_curso · finalizada). El estado se cambia manualmente (drag entre
  columnas) o lo ajusta el sistema automáticamente según start_at / due_at.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Activity(Base):
    """Actividad del tablero. Un único tablero global por tenant."""

    __tablename__ = "activities"
    __table_args__ = {"schema": "svc_tasks"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pendiente", index=True)
    # pendiente | en_curso | finalizada
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="media")
    # baja | media | alta

    # Responsable (empleado de svc_employees). Se resuelve el nombre en el frontend.
    assignee_employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Orden dentro de la columna (menor = más arriba).
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Programación para auto-transición del sistema.
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sellos reales del momento en que transicionó (manual o automático).
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

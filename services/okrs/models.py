"""OKRs service — SQLAlchemy models (C-02).

Modelo de cascada: company → team → individual con auto-referencia (parent_id).
Cumplimiento se calcula como progreso ponderado de hijos + key results del propio OKR.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Okr(Base):
    """Un OKR con jerarquía vía parent_id auto-referencia."""

    __tablename__ = "okrs"
    __table_args__ = {"schema": "svc_okrs"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("svc_okrs.okrs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Scope determina nivel de cascada
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="company")  # company|team|individual
    owner_employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    owner_department: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Objetivo (la O)
    objective: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Periodo
    period: Mapped[str] = mapped_column(String(32), nullable=False)  # ej "2026-Q3"

    # Estado calculado (semáforo) — se recalcula automáticamente
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="on-track")  # on-track|at-risk|off-track|exceeded|met
    progress: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)  # 0-100

    # Peso para agregación con padres
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KeyResult(Base):
    """Key Result (la KR). Puede estar vinculado a un KPI para auto check-in."""

    __tablename__ = "key_results"
    __table_args__ = {"schema": "svc_okrs"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    okr_id: Mapped[int] = mapped_column(
        ForeignKey("svc_okrs.okrs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False, default="numeric")  # numeric|percentage|currency|boolean
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    baseline: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    target: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    current: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)

    # C-02: enganche con KPI. Si está, los check-ins automáticos pisan current cuando el KPI se actualiza.
    linked_kpi_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OkrCheckin(Base):
    """Histórico de check-ins manuales o automáticos sobre un KR."""

    __tablename__ = "okr_checkins"
    __table_args__ = {"schema": "svc_okrs"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    kr_id: Mapped[int] = mapped_column(
        ForeignKey("svc_okrs.key_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)  # high|medium|low
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")  # manual|kpi-auto
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Plans service — SQLAlchemy models (C-03).

Un plan tiene N reglas. Cada regla define una condición JSONLogic y un cálculo
JSONLogic que se evalúa cuando la condición es true. Las reglas se evalúan en
orden por `priority`, hasta que matchea la primera (default behavior: first-match).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class CommissionPlan(Base):
    """Plan de comisiones. Reglas se evalúan contra contexto (sales, target, etc.)."""

    __tablename__ = "commission_plans"
    __table_args__ = {"schema": "svc_plans"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # A qué empleados aplica — opcional. Si vacío, "global / lo aplica el manager"
    scope_department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope_role: Mapped[str | None] = mapped_column(String(64), nullable=True)

    period: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")  # monthly|quarterly|annual
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Estrategia: "first-match" (primera regla que matchea gana) o "sum-all" (suma comisiones)
    strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="first-match")

    # Defaults para variables del contexto — útil para que el simulador no rompa
    defaults: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlanRule(Base):
    """Una regla del plan. Se evalúa `when`; si true, se calcula `amount`."""

    __tablename__ = "plan_rules"
    __table_args__ = {"schema": "svc_plans"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("svc_plans.commission_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # Condición JSONLogic — true si esta regla debe aplicarse
    when: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Cálculo JSONLogic — devuelve el importe de la comisión
    amount: Mapped[dict] = mapped_column(JSONB, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlanSimulation(Base):
    """Historial de simulaciones — útil para auditoría y para ver evolución del payout."""

    __tablename__ = "plan_simulations"
    __table_args__ = {"schema": "svc_plans"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("svc_plans.commission_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_amount: Mapped[float | None] = mapped_column(nullable=True)  # numeric
    trace: Mapped[dict] = mapped_column(JSONB, nullable=False)  # detalles de cada regla

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

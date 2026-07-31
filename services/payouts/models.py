"""Payouts service — calculadora de pagos (C-04).

Modelo:
- PayoutRun: corrida mensual/trimestral de cálculo para un departamento (o todos).
- Payout: línea individual por empleado dentro de la corrida (resultado del plan C-03).

Auditable: cada payout guarda el trace por regla aplicada (regla, condición evaluada, importe).
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class PayoutRun(Base):
    """Una corrida de cálculo. Agrupa N payouts."""

    __tablename__ = "payout_runs"
    __table_args__ = {"schema": "svc_payouts"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    plan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False)
    period_label: Mapped[str] = mapped_column(String(32), nullable=False)  # 2026-06, 2026-Q2, ...
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    department_filter: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    # draft | pending_approval | approved | paid | cancelled

    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payout(Base):
    """Línea individual de pago para un empleado."""

    __tablename__ = "payouts"
    __table_args__ = {"schema": "svc_payouts"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("svc_payouts.payout_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    employee_name: Mapped[str] = mapped_column(String(256), nullable=False)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Snapshot del contexto que se pasó al motor (sales, target, etc.)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    matched_rules: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Trace de qué reglas matchearon, qué aportaron, posibles errores
    trace: Mapped[list] = mapped_column(JSONB, nullable=False)

    # Para nómina:
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

"""Leaves service — ausencias y permisos (H-04).

Modelo:
- LeaveType: tipo de ausencia (vacaciones, enfermedad, personal, maternidad...) con reglas de devengo.
- LeaveBalance: saldo acumulado por empleado y tipo, evaluado en una fecha.
- Leave: solicitud concreta con state machine (requested → approved → taken / rejected / cancelled).

Por qué no consolidamos en una sola tabla: las reglas de devengo cambian por tipo
y por empleado (antigüedad, jornada), y mezclarlas crea queries complejas.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class LeaveType(Base):
    """Tipo de ausencia configurable por tenant."""

    __tablename__ = "leave_types"
    __table_args__ = {"schema": "svc_leaves"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(32), nullable=False)  # vacation, sick, personal, parental
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Devengo
    accrual_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="annual_grant")
    # annual_grant: N días al inicio del año
    # monthly_accrual: N/12 días por mes
    # unlimited: sin saldo (típico de enfermedad)
    # custom: regla JSON en accrual_config
    days_per_year: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    accrual_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # UX
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#02BDEA")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_negative_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Leave(Base):
    """Solicitud de ausencia concreta.

    Estados (state machine):
        requested → approved → taken
                  → rejected
                  → cancelled (desde requested o approved)
    """

    __tablename__ = "leaves"
    __table_args__ = {"schema": "svc_leaves"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(
        ForeignKey("svc_leaves.leave_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Días hábiles efectivos. Se calcula al solicitar; el motor de calendario
    # excluye fines de semana y festivos del tenant.
    business_days: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="requested")
    # requested | approved | rejected | cancelled | taken

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    requested_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # user_id
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeaveBalance(Base):
    """Snapshot del saldo de un empleado en un tipo de ausencia.

    Recalculable: se considera derivado del histórico de Leaves + accrual_strategy.
    Esta tabla cachea el resultado para no recomputar en cada query del calendario.
    """

    __tablename__ = "leave_balances"
    __table_args__ = {"schema": "svc_leaves"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    type_id: Mapped[int] = mapped_column(
        ForeignKey("svc_leaves.leave_types.id", ondelete="CASCADE"), nullable=False, index=True
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)

    accrued: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)  # devengado
    used: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    pending: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)  # solicitado sin aprobar

    # Calculados:
    # available = accrued - used - pending
    # adjustments para casos manuales (manager regaló 2 días extras, etc.)
    adjustments: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)

    last_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LeaveEvent(Base):
    """Auditoría de cambios de estado en una solicitud."""

    __tablename__ = "leave_events"
    __table_args__ = {"schema": "svc_leaves"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    leave_id: Mapped[int] = mapped_column(
        ForeignKey("svc_leaves.leaves.id", ondelete="CASCADE"), nullable=False, index=True
    )

    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

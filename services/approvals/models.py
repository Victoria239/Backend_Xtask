"""Approvals service — engine genérico de aprobaciones (C-05).

Diseño:
- Flow: plantilla que define qué entidad necesita aprobación (leave_request, payout_run, contract)
  y cuántos pasos lineales: cada paso especifica el "rol" del aprobador.
- Instance: una instancia concreta cuando se crea la entidad target.
- Step: cada nivel de aprobación dentro de la instance (pending → approved/rejected).

Soportamos roles simples por ahora: "manager_of_employee", "department_head", "admin", "specific_user".
Cuando sea pending, el sistema notifica al aprobador correspondiente.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class ApprovalFlow(Base):
    """Plantilla de flujo. Reutilizable para todas las instancias de un mismo target_kind."""

    __tablename__ = "flows"
    __table_args__ = {"schema": "svc_approvals"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # leave_request | payout_run | contract | plan_change | other

    # Si más de un flow matchea el mismo kind, gana el de mayor priority
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Filtro opcional: solo aplica si el target tiene esta condición
    filter_jsonlogic: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FlowStep(Base):
    """Pasos lineales de un flow. Posición 1, 2, 3 = orden cronológico."""

    __tablename__ = "flow_steps"
    __table_args__ = {"schema": "svc_approvals"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    flow_id: Mapped[int] = mapped_column(
        ForeignKey("svc_approvals.flows.id", ondelete="CASCADE"), nullable=False, index=True
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(32), nullable=False)
    # manager_of_employee | department_head | admin | specific_user
    approver_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # solo aplica si approver_role = "specific_user"

    auto_approve_below: Mapped[float | None] = mapped_column(nullable=True)
    # umbral opcional: si target tiene "amount" menor a este, auto-aprueba el paso
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=72)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApprovalInstance(Base):
    """Instancia activa para un target concreto (ej. leave_request id=42)."""

    __tablename__ = "instances"
    __table_args__ = {"schema": "svc_approvals"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    flow_id: Mapped[int] = mapped_column(
        ForeignKey("svc_approvals.flows.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    target_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending | approved | rejected | cancelled

    current_step_position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    requester_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Texto humano para mostrar en la bandeja: "Solicitud de vacaciones de Ana, 5 días"

    target_employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Útil para resolver "manager_of_employee" sin tener que mirar el target

    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InstanceStep(Base):
    """Cada paso concreto de una instancia: quién aprueba y cuándo."""

    __tablename__ = "instance_steps"
    __table_args__ = {"schema": "svc_approvals"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("svc_approvals.instances.id", ondelete="CASCADE"), nullable=False, index=True
    )

    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    approver_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Resuelto al crear la instance

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending | approved | rejected | skipped (por auto-approve o por skip manual)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

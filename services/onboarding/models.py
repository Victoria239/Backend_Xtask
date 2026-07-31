"""Onboarding service - SQLAlchemy models (H-02).

Modelo:
- Template: lista reusable de pasos por tenant (ej. "Default", "Engineer").
- TemplateStep: cada paso del template (order, title, due_days).
- Assignment: instancia de un template asignada a un empleado.
- AssignmentStep: estado por paso por assignment (status, completed_at).

El flujo típico:
1. Admin crea un Template con N TemplateSteps.
2. Cuando se crea un Employee nuevo, se invoca assign(template_id, employee_id):
   genera un Assignment + N AssignmentSteps en status="pending".
3. El empleado va marcando como "done" cada paso desde su /onboarding.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base


class OnboardingTemplate(Base):
    """Plantilla reusable de onboarding."""

    __tablename__ = "templates"
    __table_args__ = ({"schema": "svc_onboarding"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    steps: Mapped[list["OnboardingTemplateStep"]] = relationship(
        "OnboardingTemplateStep",
        cascade="all, delete-orphan",
        order_by="OnboardingTemplateStep.position",
    )


class OnboardingTemplateStep(Base):
    """Paso definido dentro de un template."""

    __tablename__ = "template_steps"
    __table_args__ = (
        Index("ix_tstep_template_pos", "template_id", "position"),
        {"schema": "svc_onboarding"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("svc_onboarding.templates.id", ondelete="CASCADE"), nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="general")
    due_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class OnboardingAssignment(Base):
    """Instancia del template para un empleado concreto."""

    __tablename__ = "assignments"
    __table_args__ = (
        Index("ix_assignment_tenant_emp", "tenant_id", "employee_id"),
        {"schema": "svc_onboarding"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    template_id: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["OnboardingAssignmentStep"]] = relationship(
        "OnboardingAssignmentStep",
        cascade="all, delete-orphan",
        order_by="OnboardingAssignmentStep.position",
    )


class OnboardingAssignmentStep(Base):
    """Estado de cada paso para un assignment."""

    __tablename__ = "assignment_steps"
    __table_args__ = (
        Index("ix_astep_assignment_pos", "assignment_id", "position"),
        Index("ix_astep_status", "tenant_id", "status"),
        {"schema": "svc_onboarding"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("svc_onboarding.assignments.id", ondelete="CASCADE"), nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="general")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending | in_progress | done | skipped
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

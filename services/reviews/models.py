"""Reviews 360° — SQLAlchemy models (H-05).

Ciclos por trimestre/semestre. Por empleado evaluado se asignan 4 tipos
de reviewers (self / manager / peer / report). Cada reviewer responde
preguntas con score 1-5 + comentario opcional. Al cerrar el ciclo se
calcula score agregado por categoría.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class ReviewCycle(Base):
    """Un ciclo trimestral/semestral de evaluación 360°."""
    __tablename__ = "review_cycles"
    __table_args__ = (
        Index("ix_review_cycles_tenant", "tenant_id"),
        {"schema": "svc_reviews"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # "2026-Q3"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    # open → in_progress (cuando hay respuestas) → closed (agregaciones congeladas)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewAssignment(Base):
    """Una asignación: 'reviewer evalúa a target en el ciclo X con rol Y'."""
    __tablename__ = "review_assignments"
    __table_args__ = (
        UniqueConstraint("cycle_id", "reviewer_employee_id", "target_employee_id", "role",
                         name="uq_review_assignment"),
        Index("ix_review_assign_tenant", "tenant_id"),
        Index("ix_review_assign_reviewer", "reviewer_employee_id"),
        Index("ix_review_assign_target", "target_employee_id"),
        {"schema": "svc_reviews"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewer_employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    target_employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # self|manager|peer|report
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    # pending → submitted
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewResponse(Base):
    """Respuesta individual a una pregunta. score 1-5 + comentario opcional."""
    __tablename__ = "review_responses"
    __table_args__ = (
        Index("ix_review_resp_assignment", "assignment_id"),
        Index("ix_review_resp_tenant", "tenant_id"),
        {"schema": "svc_reviews"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question_code: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewSummary(Base):
    """Score agregado por empleado al cerrar un ciclo."""
    __tablename__ = "review_summaries"
    __table_args__ = (
        UniqueConstraint("cycle_id", "employee_id", name="uq_review_summary"),
        Index("ix_review_summary_tenant", "tenant_id"),
        {"schema": "svc_reviews"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cycle_id: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_score: Mapped[float] = mapped_column(nullable=False)
    by_category: Mapped[dict] = mapped_column(JSON, nullable=False)  # {performance: 4.2, ...}
    by_role: Mapped[dict] = mapped_column(JSON, nullable=False)      # {self: 4.0, manager: 4.5, peer: 4.2}
    responses_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

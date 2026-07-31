"""ATS service — Applicant Tracking System (H-03).

Modelo:
- Pipeline: una vacante con N stages.
- Stage: columnas del kanban (Sourced, Phone screen, Tech interview, Offer, Hired/Rejected).
- Candidate: persona en el sistema, independiente del pipeline (puede aplicar a varios).
- Application: candidato ↔ pipeline ↔ stage actual.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Pipeline(Base):
    """Una vacante con su workflow de selección."""

    __tablename__ = "pipelines"
    __table_args__ = {"schema": "svc_ats"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    # open | on-hold | closed

    hiring_manager_employee_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Stage(Base):
    """Columnas del kanban. Default: cinco stages estándar al crear pipeline."""

    __tablename__ = "stages"
    __table_args__ = {"schema": "svc_ats"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("svc_ats.pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # orden visual
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Si is_terminal=True (Hired, Rejected), no se puede mover desde acá.
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#605C70")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Candidate(Base):
    """Persona independiente. Puede tener varias applications."""

    __tablename__ = "candidates"
    __table_args__ = {"schema": "svc_ats"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)

    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resume_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # linkedin | referral | website | external_recruiter | other

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Application(Base):
    """Candidato aplicando a un pipeline, parado en un stage."""

    __tablename__ = "applications"
    __table_args__ = {"schema": "svc_ats"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("svc_ats.pipelines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("svc_ats.candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("svc_ats.stages.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Cuando llegó a un terminal:
    final_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # hired | rejected | withdrawn
    expected_salary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    offered_salary: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ApplicationEvent(Base):
    """Movimientos entre stages + notas."""

    __tablename__ = "application_events"
    __table_args__ = {"schema": "svc_ats"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("svc_ats.applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # stage_change | note | interview | offer
    from_stage_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_stage_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

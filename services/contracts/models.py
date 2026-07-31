"""Contracts service — SQLAlchemy models (E-02)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Contract(Base):
    """Contrato con estados draft → review → signed → expired."""

    __tablename__ = "contracts"
    __table_args__ = {"schema": "svc_contracts"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Sujeto del contrato
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    counterparty: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Identificación
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    # ej: indefinido, temporal, freelance, NDA, comisión, confidencialidad

    # State machine: draft → review → signed → expired (o cancelled)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    # Contenido — puede venir de DocGen o pegado a mano
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Fuente
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")  # manual|docgen
    generated_doc_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Fechas
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    signed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Metadata libre (firmas, links a PDF, etc.)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Trazabilidad E-03: documentos del corpus que respaldaron este contrato
    # [{document_id, document_title, snippet, score}]
    source_documents: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    # E-04: eSign
    esign_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # docusign | mock | None
    esign_envelope_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    esign_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # created | sent | delivered | completed | declined | voided
    esign_signing_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    esign_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    esign_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    esign_signer_email: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Alertas ya emitidas — evita duplicados (60, 30, 15)
    alerts_sent: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContractEvent(Base):
    """Auditoría de transiciones de estado."""

    __tablename__ = "contract_events"
    __table_args__ = {"schema": "svc_contracts"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("svc_contracts.contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # status_change|alert|signed|note
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

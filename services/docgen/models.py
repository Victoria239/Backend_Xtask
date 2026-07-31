"""DocGen service - SQLAlchemy models (AI-03 generación documental con RAG).

Modelo:
- DocTemplate: plantilla Jinja2 (markdown body con placeholders).
- GeneratedDoc: documento generado a partir de un template + employee + custom_context.
  El cuerpo final se guarda como markdown + html (sin PDF en MVP — más adelante).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class DocTemplate(Base):
    """Plantilla reusable de generación documental."""

    __tablename__ = "doc_templates"
    __table_args__ = ({"schema": "svc_docgen"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="general")
    # body: markdown con {{placeholders}} estilo Jinja2.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # rag_query opcional: si está, se hace una búsqueda en el corpus
    # y los top chunks se inyectan al rendering como "rag" context.
    rag_query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )


class GeneratedDoc(Base):
    """Documento generado a partir de un template, asociado a un empleado."""

    __tablename__ = "generated_docs"
    __table_args__ = (
        Index("ix_gendoc_tenant_emp", "tenant_id", "employee_id"),
        {"schema": "svc_docgen"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("svc_docgen.doc_templates.id", ondelete="SET NULL"), nullable=True,
    )
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    # citations[] guardado como JSON list con {document_id, document_title, score, snippet}
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # custom_context que el user pasó al generar
    custom_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

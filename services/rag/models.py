"""RAG service - SQLAlchemy models using pgvector.

Multi-tenant isolation is enforced via mandatory `tenant_id` on every row.
All queries MUST filter by tenant_id at the repository layer.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base
from services.rag import EMBEDDING_DIM


class Document(Base):
    """A document ingested into the corpus of a tenant.

    A document can be a policy PDF, an HR template, a contract sample, a compensation
    matrix, or any free-form text that should feed the RAG pipeline.
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_tenant_source", "tenant_id", "source_type"),
        {"schema": "svc_rag"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="raw")
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="es")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|chunked|embedded|failed
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Chunk(Base):
    """A semantically chunked piece of a Document, with its embedding vector."""

    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_doc_position", "document_id", "position"),
        # IVFFlat ANN index is created via raw SQL in the Alembic migration once
        # there is enough data to train it. For dev/empty DB we leave only the
        # standard tenant_id btree index here.
        Index("ix_chunks_tenant", "tenant_id"),
        {"schema": "svc_rag"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    """Tracks an async ingestion job for observability."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = {"schema": "svc_rag"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embeddings_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

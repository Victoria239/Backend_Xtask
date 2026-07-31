"""Phase 1: tenants + RAG infrastructure + HRM/KPI extensions.

Revision ID: 004
Revises: 003
Create Date: 2026-06-09 14:30:00.000000

Adds:
  - pgvector extension
  - svc_tenants schema + tenants & tenant_memberships
  - svc_rag schema + documents, chunks (with vector), ingestion_jobs
  - svc_ai schema + conversations, messages (AI-08)
  - employees: tenant_id, manager_id, hire_date, custom_fields + employee_documents
  - kpis: tenant_id, metric_type, unit, weight, periodicity + kpi_measurements
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. New schemas
    for schema in ("svc_tenants", "svc_rag", "svc_ai"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # 3. Tenants (P-01)
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True, unique=True),
        sa.Column("plan", sa.String(32), nullable=False, server_default="startup"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("settings", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_tenants",
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], schema="svc_tenants")

    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_tenants",
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"], schema="svc_tenants")
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"], schema="svc_tenants")

    # 4. RAG (AI-01, AI-02)
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(64), nullable=False, server_default="raw"),
        sa.Column("source_uri", sa.Text, nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="es"),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_rag",
    )
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"], schema="svc_rag")
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"], schema="svc_rag")
    op.create_index("ix_documents_tenant_source", "documents", ["tenant_id", "source_type"], schema="svc_rag")

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("document_id", sa.Integer, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_model", sa.String(64), nullable=True),
        sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_rag",
    )
    op.create_index("ix_chunks_tenant", "chunks", ["tenant_id"], schema="svc_rag")
    op.create_index("ix_chunks_doc_position", "chunks", ["document_id", "position"], schema="svc_rag")

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("document_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("chunks_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embeddings_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="svc_rag",
    )
    op.create_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", ["tenant_id"], schema="svc_rag")

    # 5. AI Assistant (AI-08)
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_ai",
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"], schema="svc_ai")
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"], schema="svc_ai")

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("conversation_id", sa.Integer, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_ai",
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"], schema="svc_ai")
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"], schema="svc_ai")

    # 6. Employees extensions (H-01)
    op.add_column("employees", sa.Column("tenant_id", sa.Integer, nullable=True), schema="svc_employees")
    op.add_column("employees", sa.Column("manager_id", sa.Integer, nullable=True), schema="svc_employees")
    op.add_column("employees", sa.Column("hire_date", sa.Date, nullable=True), schema="svc_employees")
    op.add_column(
        "employees",
        sa.Column("custom_fields", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        schema="svc_employees",
    )
    op.create_index("ix_employees_tenant_id", "employees", ["tenant_id"], schema="svc_employees")
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"], schema="svc_employees")

    op.create_table(
        "employee_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=True),
        sa.Column("employee_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("doc_type", sa.String(64), nullable=False, server_default="other"),
        sa.Column("storage_uri", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("meta", sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="svc_employees",
    )
    op.create_index("ix_employee_documents_employee_id", "employee_documents", ["employee_id"], schema="svc_employees")
    op.create_index("ix_employee_documents_tenant_id", "employee_documents", ["tenant_id"], schema="svc_employees")

    # 7. KPI extensions (C-01)
    op.add_column("kpis", sa.Column("tenant_id", sa.Integer, nullable=True), schema="svc_kpis")
    op.add_column("kpis", sa.Column("metric_type", sa.String(32), nullable=False, server_default="numeric"), schema="svc_kpis")
    op.add_column("kpis", sa.Column("unit", sa.String(32), nullable=True), schema="svc_kpis")
    op.add_column("kpis", sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="1.0"), schema="svc_kpis")
    op.add_column("kpis", sa.Column("periodicity", sa.String(16), nullable=False, server_default="monthly"), schema="svc_kpis")
    op.create_index("ix_kpis_tenant_id", "kpis", ["tenant_id"], schema="svc_kpis")

    op.create_table(
        "kpi_measurements",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer, nullable=True),
        sa.Column("kpi_id", sa.Integer, nullable=False),
        sa.Column("value", sa.Numeric(14, 4), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        schema="svc_kpis",
    )
    op.create_index("ix_kpi_measurements_kpi_id", "kpi_measurements", ["kpi_id"], schema="svc_kpis")
    op.create_index("ix_kpi_measurements_tenant_id", "kpi_measurements", ["tenant_id"], schema="svc_kpis")


def downgrade() -> None:
    op.drop_index("ix_kpi_measurements_tenant_id", "kpi_measurements", schema="svc_kpis")
    op.drop_index("ix_kpi_measurements_kpi_id", "kpi_measurements", schema="svc_kpis")
    op.drop_table("kpi_measurements", schema="svc_kpis")
    op.drop_index("ix_kpis_tenant_id", "kpis", schema="svc_kpis")
    for col in ("periodicity", "weight", "unit", "metric_type", "tenant_id"):
        op.drop_column("kpis", col, schema="svc_kpis")

    op.drop_index("ix_employee_documents_tenant_id", "employee_documents", schema="svc_employees")
    op.drop_index("ix_employee_documents_employee_id", "employee_documents", schema="svc_employees")
    op.drop_table("employee_documents", schema="svc_employees")
    op.drop_index("ix_employees_manager_id", "employees", schema="svc_employees")
    op.drop_index("ix_employees_tenant_id", "employees", schema="svc_employees")
    for col in ("custom_fields", "hire_date", "manager_id", "tenant_id"):
        op.drop_column("employees", col, schema="svc_employees")

    op.drop_index("ix_messages_tenant_id", "messages", schema="svc_ai")
    op.drop_index("ix_messages_conversation_id", "messages", schema="svc_ai")
    op.drop_table("messages", schema="svc_ai")
    op.drop_index("ix_conversations_user_id", "conversations", schema="svc_ai")
    op.drop_index("ix_conversations_tenant_id", "conversations", schema="svc_ai")
    op.drop_table("conversations", schema="svc_ai")

    op.drop_index("ix_ingestion_jobs_tenant_id", "ingestion_jobs", schema="svc_rag")
    op.drop_table("ingestion_jobs", schema="svc_rag")
    op.drop_index("ix_chunks_doc_position", "chunks", schema="svc_rag")
    op.drop_index("ix_chunks_tenant", "chunks", schema="svc_rag")
    op.drop_table("chunks", schema="svc_rag")
    op.drop_index("ix_documents_tenant_source", "documents", schema="svc_rag")
    op.drop_index("ix_documents_content_hash", "documents", schema="svc_rag")
    op.drop_index("ix_documents_tenant_id", "documents", schema="svc_rag")
    op.drop_table("documents", schema="svc_rag")

    op.drop_index("ix_tenant_memberships_user_id", "tenant_memberships", schema="svc_tenants")
    op.drop_index("ix_tenant_memberships_tenant_id", "tenant_memberships", schema="svc_tenants")
    op.drop_table("tenant_memberships", schema="svc_tenants")
    op.drop_index("ix_tenants_slug", "tenants", schema="svc_tenants")
    op.drop_table("tenants", schema="svc_tenants")

    op.execute("DROP SCHEMA IF EXISTS svc_ai CASCADE")
    op.execute("DROP SCHEMA IF EXISTS svc_rag CASCADE")
    op.execute("DROP SCHEMA IF EXISTS svc_tenants CASCADE")

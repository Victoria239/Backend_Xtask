"""DocGen service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


# ─── Templates ─────────────────────────────────────────────
class TemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str = "general"
    body: str = Field(..., min_length=1)
    rag_query: str | None = None


class TemplateOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: str | None
    category: str
    body: str
    rag_query: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Generation ────────────────────────────────────────────
class GenerateRequest(BaseModel):
    template_id: int
    employee_id: int
    custom_context: dict = Field(default_factory=dict)
    title: str | None = None             # si None, usa template.name + employee.name


class Citation(BaseModel):
    document_id: int
    document_title: str
    snippet: str
    score: float


class GeneratedDocOut(BaseModel):
    id: int
    tenant_id: int
    template_id: int | None
    template_name: str
    employee_id: int
    title: str
    body_md: str
    body_html: str
    citations: list[Citation] = []
    custom_context: dict = {}
    created_by: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GeneratedDocSummary(BaseModel):
    """Listado: solo metadata, sin el cuerpo (es pesado)."""
    id: int
    template_id: int | None
    template_name: str
    employee_id: int
    title: str
    citation_count: int
    created_at: datetime

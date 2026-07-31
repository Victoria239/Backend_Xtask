"""RAG service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class IngestTextRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    content: str = Field(..., min_length=1)
    source_type: str = "raw"
    source_uri: str | None = None
    mime_type: str | None = "text/plain"
    language: str = "es"
    meta: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: int
    chunks: int
    embedded: int
    status: str
    provider: str | None = None


class DocumentOut(BaseModel):
    id: int
    tenant_id: int
    title: str
    source_type: str
    source_uri: str | None
    mime_type: str | None
    language: str
    status: str
    meta: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=25)


class SearchHit(BaseModel):
    document_id: int
    document_title: str
    position: int
    content: str
    score: float
    meta: dict
    source_type: str = "raw"
    source_uri: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]

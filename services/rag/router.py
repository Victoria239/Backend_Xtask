"""RAG service - HTTP routes (AI-02 ingestion + retrieval endpoints)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_tenant_id, get_current_user_id, require_manager
from services.rag.repository import RagRepository
from services.rag.service import RagService
from services.rag.schemas import (
    DocumentOut,
    IngestResponse,
    IngestTextRequest,
    SearchHit,
    SearchRequest,
    SearchResponse,
)

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("rag"))) -> RagService:
    return RagService(RagRepository(db))


# ─── Ingestion ──────────────────────────────────────────────────
@router.post("/ingest/text", response_model=IngestResponse, dependencies=[Depends(require_manager)])
async def ingest_text(
    payload: IngestTextRequest,
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.ingest_text(
        tenant_id=tenant_id,
        title=payload.title,
        content=payload.content,
        source_type=payload.source_type,
        source_uri=payload.source_uri,
        mime_type=payload.mime_type,
        language=payload.language,
        meta={**payload.meta, "uploaded_by": user_id},
    )


@router.post("/ingest/file", response_model=IngestResponse, dependencies=[Depends(require_manager)])
async def ingest_file(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    language: str = Form("es"),
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    """Multi-format ingestion. Supports text/* and falls back to UTF-8 decode for others.

    PDF/docx extraction is delegated to a future worker (TODO AI-02 phase 2).
    """
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    return await service.ingest_text(
        tenant_id=tenant_id,
        title=title or file.filename or "uploaded-document",
        content=text,
        source_type="upload",
        source_uri=file.filename,
        mime_type=file.content_type,
        language=language,
        meta={"uploaded_by": user_id, "size_bytes": len(raw)},
    )


# ─── Corpus management ──────────────────────────────────────────
@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_documents(tenant_id)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.get_document(tenant_id, document_id)


@router.delete("/documents/{document_id}", status_code=204, dependencies=[Depends(require_manager)])
async def delete_document(
    document_id: int,
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    await service.delete_document(tenant_id, document_id)


# ─── Retrieval ──────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    service: RagService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    hits = await service.search(tenant_id, payload.query, top_k=payload.top_k)
    return SearchResponse(
        query=payload.query,
        hits=[
            SearchHit(
                document_id=h.document_id,
                document_title=h.document_title,
                position=h.position,
                content=h.content,
                score=h.score,
                meta=h.meta,
                source_type=h.source_type,
                source_uri=h.source_uri,
            )
            for h in hits
        ],
    )

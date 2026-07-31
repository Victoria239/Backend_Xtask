"""RAG service - orchestration of ingestion + retrieval (AI-01, AI-02)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from shared.exceptions import NotFoundException
from shared.notifications import emit_notification
from services.rag.chunker import chunk_text
from services.rag.embeddings import EmbeddingProvider, embed_batch, get_embedding_provider
from services.rag.models import Chunk
from services.rag.repository import RagRepository


@dataclass
class RetrievedChunk:
    document_id: int
    document_title: str
    position: int
    content: str
    score: float  # 1 - cosine_distance, in [-1, 1]
    meta: dict
    source_type: str = "raw"
    source_uri: str | None = None


class RagService:
    def __init__(self, repo: RagRepository, provider: EmbeddingProvider | None = None):
        self.repo = repo
        self.provider = provider or get_embedding_provider()

    # ─── Ingestion (AI-02) ──────────────────────────────────
    async def ingest_text(
        self,
        tenant_id: int,
        title: str,
        content: str,
        *,
        source_type: str = "raw",
        source_uri: str | None = None,
        mime_type: str | None = "text/plain",
        language: str = "es",
        meta: dict | None = None,
    ) -> dict:
        meta = meta or {}
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        doc = await self.repo.create_document(
            tenant_id=tenant_id,
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            mime_type=mime_type,
            language=language,
            content_hash=content_hash,
            status="chunking",
            meta=meta,
        )
        job = await self.repo.create_job(tenant_id=tenant_id, document_id=doc.id)

        try:
            pieces = chunk_text(content)
            if not pieces:
                await self.repo.set_document_status(tenant_id, doc.id, "failed")
                await self.repo.update_job(
                    job.id, status="failed", error="empty content after chunking",
                    finished_at=datetime.now(timezone.utc),
                )
                return {"document_id": doc.id, "chunks": 0, "embedded": 0, "status": "failed"}

            embeddings = await embed_batch(self.provider, [p.content for p in pieces])

            chunk_meta_base = {"source_type": source_type, "source_uri": source_uri}
            chunk_rows = [
                Chunk(
                    tenant_id=tenant_id,
                    document_id=doc.id,
                    position=p.position,
                    content=p.content,
                    token_count=p.token_count,
                    embedding=emb,
                    embedding_model=self.provider.name,
                    meta=chunk_meta_base,
                )
                for p, emb in zip(pieces, embeddings)
            ]
            await self.repo.bulk_insert_chunks(chunk_rows)
            await self.repo.set_document_status(tenant_id, doc.id, "embedded")
            await self.repo.update_job(
                job.id,
                status="completed",
                chunks_created=len(chunk_rows),
                embeddings_created=len(chunk_rows),
                finished_at=datetime.now(timezone.utc),
            )

            # P-04: notif al user que subió el doc
            uploaded_by = meta.get("uploaded_by") if isinstance(meta, dict) else None
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id,
                user_id=uploaded_by,
                title=f'Documento "{title}" indexado',
                body=f"{len(chunk_rows)} fragmento{'s' if len(chunk_rows) != 1 else ''} listo{'s' if len(chunk_rows) != 1 else ''} para el copiloto. Ya podés citarlo desde el asistente.",
                kind="success",
                category="rag",
                action_url="/documentos",
                meta={"document_id": doc.id, "chunks": len(chunk_rows)},
            )

            return {
                "document_id": doc.id,
                "chunks": len(chunk_rows),
                "embedded": len(chunk_rows),
                "status": "embedded",
                "provider": self.provider.name,
            }
        except Exception as exc:  # noqa: BLE001
            await self.repo.set_document_status(tenant_id, doc.id, "failed")
            await self.repo.update_job(
                job.id, status="failed", error=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
            raise

    async def list_documents(self, tenant_id: int):
        return await self.repo.list_documents(tenant_id)

    async def get_document(self, tenant_id: int, document_id: int):
        doc = await self.repo.get_document(tenant_id, document_id)
        if not doc:
            raise NotFoundException("Document", document_id)
        return doc

    async def delete_document(self, tenant_id: int, document_id: int) -> None:
        deleted = await self.repo.delete_document(tenant_id, document_id)
        if not deleted:
            raise NotFoundException("Document", document_id)

    # ─── Retrieval (AI-08, AI-03 foundation) ────────────────
    async def search(
        self,
        tenant_id: int,
        query: str,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        if not query.strip():
            return []
        # Sprint 7: medir tiempo de búsqueda
        try:
            from shared.metrics import RAG_SEARCH_SECONDS
            _t = RAG_SEARCH_SECONDS.time()
            _t.__enter__()
        except Exception:  # noqa: BLE001
            _t = None
        [query_vec] = await self.provider.embed([query])
        rows = await self.repo.search_similar(tenant_id, query_vec, top_k=top_k)
        if _t:
            try:
                _t.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass

        # We need document titles + source — fetch once per unique document
        doc_meta_cache: dict[int, tuple[str, str, str | None]] = {}
        for chunk, _ in rows:
            if chunk.document_id not in doc_meta_cache:
                doc = await self.repo.get_document(tenant_id, chunk.document_id)
                if doc:
                    doc_meta_cache[chunk.document_id] = (doc.title, doc.source_type, doc.source_uri)
                else:
                    doc_meta_cache[chunk.document_id] = ("(unknown)", "raw", None)

        return [
            RetrievedChunk(
                document_id=chunk.document_id,
                document_title=doc_meta_cache[chunk.document_id][0],
                position=chunk.position,
                content=chunk.content,
                score=1.0 - distance,
                meta=chunk.meta or {},
                source_type=doc_meta_cache[chunk.document_id][1],
                source_uri=doc_meta_cache[chunk.document_id][2],
            )
            for chunk, distance in rows
        ]

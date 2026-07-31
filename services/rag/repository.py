"""RAG repository - all access enforces tenant_id filtering."""

from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.rag.models import Chunk, Document, IngestionJob


class RagRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Documents ──────────────────────────────────────────
    async def create_document(self, tenant_id: int, **fields) -> Document:
        doc = Document(tenant_id=tenant_id, **fields)
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def get_document(self, tenant_id: int, document_id: int) -> Document | None:
        res = await self.db.execute(
            select(Document).where(Document.tenant_id == tenant_id, Document.id == document_id)
        )
        return res.scalar_one_or_none()

    async def list_documents(self, tenant_id: int, limit: int = 100) -> list[Document]:
        res = await self.db.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())

    async def set_document_status(self, tenant_id: int, document_id: int, status: str) -> None:
        doc = await self.get_document(tenant_id, document_id)
        if doc:
            doc.status = status
            await self.db.flush()

    async def delete_document(self, tenant_id: int, document_id: int) -> bool:
        doc = await self.get_document(tenant_id, document_id)
        if not doc:
            return False
        await self.db.execute(
            delete(Chunk).where(Chunk.tenant_id == tenant_id, Chunk.document_id == document_id)
        )
        await self.db.delete(doc)
        await self.db.flush()
        return True

    # ─── Chunks ─────────────────────────────────────────────
    async def bulk_insert_chunks(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            self.db.add(c)
        await self.db.flush()

    async def search_similar(
        self,
        tenant_id: int,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        """Cosine-similarity search restricted to a single tenant.

        Returns (chunk, distance) tuples ordered by ascending distance.
        """
        # pgvector cosine distance operator is <=>
        stmt = (
            select(Chunk, Chunk.embedding.cosine_distance(query_embedding).label("distance"))
            .where(Chunk.tenant_id == tenant_id, Chunk.embedding.isnot(None))
            .order_by("distance")
            .limit(top_k)
        )
        res = await self.db.execute(stmt)
        return [(row[0], float(row[1])) for row in res.all()]

    # ─── Jobs ───────────────────────────────────────────────
    async def create_job(self, tenant_id: int, document_id: int | None = None) -> IngestionJob:
        job = IngestionJob(tenant_id=tenant_id, document_id=document_id, status="queued")
        self.db.add(job)
        await self.db.flush()
        return job

    async def update_job(self, job_id: int, **fields) -> None:
        res = await self.db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        job = res.scalar_one_or_none()
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        await self.db.flush()

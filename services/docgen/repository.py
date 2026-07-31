"""DocGen service - DB repository."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.docgen.models import DocTemplate, GeneratedDoc


class DocGenRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Templates ────────────────────────────────────────
    async def list_templates(self, tenant_id: int) -> list[DocTemplate]:
        stmt = (
            select(DocTemplate)
            .where(DocTemplate.tenant_id == tenant_id)
            .order_by(DocTemplate.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_template(self, tenant_id: int, template_id: int) -> DocTemplate | None:
        stmt = select(DocTemplate).where(
            DocTemplate.tenant_id == tenant_id, DocTemplate.id == template_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_template(self, tenant_id: int, data: dict, created_by: int | None) -> DocTemplate:
        tpl = DocTemplate(tenant_id=tenant_id, created_by=created_by, **data)
        self.db.add(tpl)
        await self.db.flush()
        await self.db.refresh(tpl)
        return tpl

    async def update_template(self, tenant_id: int, template_id: int, data: dict) -> DocTemplate | None:
        tpl = await self.get_template(tenant_id, template_id)
        if not tpl:
            return None
        for k, v in data.items():
            setattr(tpl, k, v)
        await self.db.flush()
        return tpl

    async def delete_template(self, tenant_id: int, template_id: int) -> bool:
        tpl = await self.get_template(tenant_id, template_id)
        if not tpl:
            return False
        await self.db.delete(tpl)
        return True

    # ─── Generated docs ───────────────────────────────────
    async def list_generated(
        self, tenant_id: int, employee_id: int | None = None,
    ) -> list[GeneratedDoc]:
        stmt = (
            select(GeneratedDoc)
            .where(GeneratedDoc.tenant_id == tenant_id)
            .order_by(GeneratedDoc.created_at.desc())
        )
        if employee_id:
            stmt = stmt.where(GeneratedDoc.employee_id == employee_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_generated(self, tenant_id: int, doc_id: int) -> GeneratedDoc | None:
        stmt = select(GeneratedDoc).where(
            GeneratedDoc.tenant_id == tenant_id, GeneratedDoc.id == doc_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_generated(self, data: dict) -> GeneratedDoc:
        doc = GeneratedDoc(**data)
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)
        return doc

    async def delete_generated(self, tenant_id: int, doc_id: int) -> bool:
        result = await self.db.execute(
            delete(GeneratedDoc).where(
                GeneratedDoc.tenant_id == tenant_id, GeneratedDoc.id == doc_id,
            )
        )
        return (result.rowcount or 0) > 0

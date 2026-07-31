"""DocGen service - business logic (AI-03).

Pipeline de generación:
1. Cargar el template (Jinja2 markdown).
2. Resolver context:
   - employee: datos del empleado (svc_employees.employees)
   - custom_context: dict que el user pasó al endpoint
   - rag.results: si el template tiene rag_query, busca en svc_rag y mete top-K
3. Renderizar Jinja → markdown.
4. Convertir markdown → HTML sanitizado (bleach).
5. Persistir GeneratedDoc con cuerpo + citations.
"""

from __future__ import annotations

from typing import Any

import bleach
import markdown as md
from jinja2 import Environment, StrictUndefined, select_autoescape
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.exceptions import NotFoundException
from services.docgen.models import GeneratedDoc
from services.docgen.repository import DocGenRepository
from services.docgen.schemas import GenerateRequest, TemplateIn

# RAG access — usamos el repo del rag service directo para evitar HTTP entre servicios.
from services.rag.repository import RagRepository
from services.rag.service import RagService

ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "b", "i", "u", "del", "s",
    "ul", "ol", "li",
    "blockquote", "code", "pre",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "sup", "sub",
    "span", "div",
]
ALLOWED_ATTRS = {
    "*": ["class", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
}


class _NullCtx:
    """Context manager no-op para reemplazar el timer Prometheus cuando no está disponible."""
    def __enter__(self): return self
    def __exit__(self, *_): return False


class DocGenService:
    def __init__(self, repo: DocGenRepository):
        self.repo = repo
        self._jinja = Environment(
            autoescape=select_autoescape(default_for_string=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ─── Templates ────────────────────────────────────────
    async def list_templates(self, tenant_id: int):
        return await self.repo.list_templates(tenant_id)

    async def create_template(self, tenant_id: int, payload: TemplateIn, user_id: int | None):
        return await self.repo.create_template(tenant_id, payload.model_dump(), user_id)

    async def update_template(self, tenant_id: int, template_id: int, payload: TemplateIn):
        tpl = await self.repo.update_template(tenant_id, template_id, payload.model_dump())
        if not tpl:
            raise NotFoundException("Template", template_id)
        return tpl

    async def delete_template(self, tenant_id: int, template_id: int) -> None:
        ok = await self.repo.delete_template(tenant_id, template_id)
        if not ok:
            raise NotFoundException("Template", template_id)

    # ─── Generation ──────────────────────────────────────
    async def generate(
        self, tenant_id: int, payload: GenerateRequest, user_id: int | None,
    ) -> GeneratedDoc:
        # Prometheus histogram timer — context manager para no leakear samples
        # si una excepción interrumpe el flujo.
        try:
            from shared.metrics import DOCGEN_GENERATION_SECONDS
            timer_cm = DOCGEN_GENERATION_SECONDS.labels(template_id=str(payload.template_id)).time()
        except Exception:  # noqa: BLE001
            timer_cm = _NullCtx()

        with timer_cm:
            # 1) Template
            tpl = await self.repo.get_template(tenant_id, payload.template_id)
            if not tpl:
                raise NotFoundException("Template", payload.template_id)

            # 2) Empleado (raw SQL para evitar coupling de modelos cross-service)
            employee = await self._load_employee(tenant_id, payload.employee_id)
            if not employee:
                raise NotFoundException("Employee", payload.employee_id)

            # 3) RAG context — buscar en svc_rag si el template tiene rag_query
            rag_hits: list[dict] = []
            if tpl.rag_query:
                # Sustituimos placeholders Jinja en el rag_query primero (puede tener {{employee.position}})
                try:
                    resolved_query = self._jinja.from_string(tpl.rag_query).render(
                        employee=employee, custom=payload.custom_context,
                    )
                except Exception:
                    resolved_query = tpl.rag_query
                rag_hits = await self._search_rag(tenant_id, resolved_query, top_k=4)

            # 4) Render Jinja → markdown
            context = {
                "employee": employee,
                "custom": payload.custom_context,
                "rag": {
                    "results": rag_hits,
                    "block": _format_rag_block(rag_hits),
                },
            }
            try:
                body_md = self._jinja.from_string(tpl.body).render(**context)
            except Exception as e:
                raise ValueError(f"Error renderizando template: {e}") from e

            # 5) Markdown → HTML sanitizado
            html_raw = md.markdown(body_md, extensions=["extra", "sane_lists", "smarty"])
            body_html = bleach.clean(html_raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)

            # 6) Citations subset (lo que mostramos en UI/metadata)
            citations = [
                {
                    "document_id": h["document_id"],
                    "document_title": h["document_title"],
                    "snippet": h["snippet"][:300],
                    "score": float(h["score"]),
                }
                for h in rag_hits
            ]

            # 7) Title
            if payload.title:
                title = payload.title
            else:
                title = f"{tpl.name} · {employee['first_name']} {employee['last_name']}"

            # 8) Persist
            doc = await self.repo.create_generated({
                "tenant_id": tenant_id,
                "template_id": tpl.id,
                "template_name": tpl.name,
                "employee_id": employee["id"],
                "title": title,
                "body_md": body_md,
                "body_html": body_html,
                "citations": citations,
                "custom_context": payload.custom_context or {},
                "created_by": user_id,
            })
            return doc

    async def list_generated(self, tenant_id: int, employee_id: int | None = None):
        return await self.repo.list_generated(tenant_id, employee_id)

    async def get_generated(self, tenant_id: int, doc_id: int) -> GeneratedDoc:
        doc = await self.repo.get_generated(tenant_id, doc_id)
        if not doc:
            raise NotFoundException("GeneratedDoc", doc_id)
        return doc

    async def delete_generated(self, tenant_id: int, doc_id: int) -> None:
        ok = await self.repo.delete_generated(tenant_id, doc_id)
        if not ok:
            raise NotFoundException("GeneratedDoc", doc_id)

    # ─── Helpers ─────────────────────────────────────────
    async def _load_employee(self, tenant_id: int, employee_id: int) -> dict | None:
        result = await self.repo.db.execute(sql_text("""
            SELECT id, first_name, last_name, position, department, salary,
                   contract_status, hire_date, custom_fields
            FROM svc_employees.employees
            WHERE id = :eid AND tenant_id = :tid
            LIMIT 1
        """), {"eid": employee_id, "tid": tenant_id})
        row = result.mappings().first()
        if not row:
            return None
        return dict(row)

    async def _search_rag(self, tenant_id: int, query: str, top_k: int = 4) -> list[dict]:
        """Reusa el rag service para que comparta provider/configuración."""
        rag_service = RagService(RagRepository(self.repo.db))
        try:
            hits = await rag_service.search(tenant_id, query, top_k=top_k)
        except Exception:
            return []
        return [
            {
                "document_id": h.document_id,
                "document_title": h.document_title,
                "content": h.content,
                "snippet": h.content[:280],
                "score": float(h.score),
                "position": h.position,
            }
            for h in hits
        ]


def _format_rag_block(hits: list[dict]) -> str:
    """Block markdown con las citas extraídas del corpus, listo para inyectar
    en el template como ``{{ rag.block }}``."""
    if not hits:
        return ""
    lines = ["", "## Referencias del corpus", ""]
    for i, h in enumerate(hits, start=1):
        title = h["document_title"]
        snippet = h["snippet"].strip().replace("\n", " ")
        lines.append(f"**[{i}] {title}** — \"{snippet}\"")
        lines.append("")
    return "\n".join(lines)

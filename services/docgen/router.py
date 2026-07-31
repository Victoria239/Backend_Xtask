"""DocGen service - HTTP routes (AI-03)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    require_admin,
    require_manager,
)
from services.docgen.repository import DocGenRepository
from services.docgen.schemas import (
    GenerateRequest,
    GeneratedDocOut,
    GeneratedDocSummary,
    TemplateIn,
    TemplateOut,
)
from services.docgen.service import DocGenService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("docgen"))) -> DocGenService:
    return DocGenService(DocGenRepository(db))


# ─── Templates ──────────────────────────────────────────
@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_templates(tenant_id)


@router.post("/templates", response_model=TemplateOut, dependencies=[Depends(require_manager)])
async def create_template(
    payload: TemplateIn,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create_template(tenant_id, payload, user_id)


@router.put(
    "/templates/{template_id}",
    response_model=TemplateOut,
    dependencies=[Depends(require_manager)],
)
async def update_template(
    template_id: int,
    payload: TemplateIn,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.update_template(tenant_id, template_id, payload)


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
async def delete_template(
    template_id: int,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    await service.delete_template(tenant_id, template_id)


# ─── Generation ─────────────────────────────────────────
@router.post(
    "/generate",
    response_model=GeneratedDocOut,
    dependencies=[Depends(require_manager)],
)
async def generate(
    payload: GenerateRequest,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.generate(tenant_id, payload, user_id)
    except ValueError as e:
        # Errores de renderizado (vars faltantes en custom_context, RAG sin resultados, etc.)
        raise HTTPException(status_code=400, detail=str(e)) from e


# ─── Seed templates pre-configurados (E-03) — requiere admin ─────────────────────────────────────────
@router.post("/seed-contract-templates", dependencies=[Depends(require_admin)])
async def seed_contract_templates_endpoint(
    tenant_id: int = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_service_db("docgen")),
):
    from services.docgen.seed_templates import seed_contract_templates
    result = await seed_contract_templates(db, tenant_id)
    return result


# ─── Internal: invocable desde otros servicios (sin auth, takes tenant explícito) ─────────────────────────────────────────
@router.post("/internal/generate", response_model=GeneratedDocOut)
async def internal_generate(
    payload: GenerateRequest,
    tenant_id: int = Query(...),
    user_id: int | None = Query(None),
    service: DocGenService = Depends(get_service),
):
    """Endpoint interno para que otros servicios (e.g. contracts) usen DocGen sin JWT."""
    try:
        return await service.generate(tenant_id, payload, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/documents", response_model=list[GeneratedDocSummary])
async def list_documents(
    employee_id: int | None = Query(None),
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    items = await service.list_generated(tenant_id, employee_id)
    return [
        GeneratedDocSummary(
            id=d.id,
            template_id=d.template_id,
            template_name=d.template_name,
            employee_id=d.employee_id,
            title=d.title,
            citation_count=len(d.citations or []),
            created_at=d.created_at,
        )
        for d in items
    ]


@router.get("/documents/{doc_id}", response_model=GeneratedDocOut)
async def get_document(
    doc_id: int,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.get_generated(tenant_id, doc_id)


@router.delete("/documents/{doc_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_document(
    doc_id: int,
    service: DocGenService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    await service.delete_generated(tenant_id, doc_id)

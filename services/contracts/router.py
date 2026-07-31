"""Contracts service — HTTP routes (E-02)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import (
    get_current_tenant_id,
    get_current_user_id,
    require_admin,
    require_manager,
)
from services.contracts.repository import ContractRepository
from services.contracts.esign import current_mode as esign_current_mode
from services.contracts.schemas import (
    ContractEventOut,
    ContractFromDocgen,
    ContractIn,
    ContractOut,
    ContractSummary,
    ContractUpdate,
    ESignResult,
    ExpiryAlertResult,
    GenerateContractRequest,
    MockSignConfirm,
    SendForSigning,
    StatusTransition,
)
from services.contracts.service import ContractService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("contracts"))) -> ContractService:
    return ContractService(ContractRepository(db))


@router.get("/", response_model=list[ContractSummary])
async def list_contracts(
    status: str | None = Query(None),
    employee_id: int | None = Query(None),
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return await service.list_contracts(tenant_id, status, employee_id)


@router.get("/{contract_id}", response_model=ContractOut)
async def get_contract(
    contract_id: int,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    c = await service.get_contract(tenant_id, contract_id)
    if not c:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return c


@router.get("/{contract_id}/events", response_model=list[ContractEventOut])
async def list_events(
    contract_id: int,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        return await service.list_events(tenant_id, contract_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/", response_model=ContractOut, dependencies=[Depends(require_manager)])
async def create_contract(
    payload: ContractIn,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.create(tenant_id, user_id, payload)


@router.post(
    "/from-docgen", response_model=ContractOut, dependencies=[Depends(require_manager)]
)
async def create_from_docgen(
    payload: ContractFromDocgen,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.create_from_docgen(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/generate", response_model=ContractOut, dependencies=[Depends(require_manager)]
)
async def generate_contract(
    payload: GenerateContractRequest,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    """E-03: combina DocGen + RAG + persistencia como contrato en una sola llamada."""
    try:
        return await service.generate_contract(tenant_id, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put(
    "/{contract_id}", response_model=ContractOut, dependencies=[Depends(require_manager)]
)
async def update_contract(
    contract_id: int,
    payload: ContractUpdate,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        out = await service.update(tenant_id, contract_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not out:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return out


@router.delete("/{contract_id}", dependencies=[Depends(require_admin)])
async def delete_contract(
    contract_id: int,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    try:
        ok = await service.delete(tenant_id, contract_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")
    return {"ok": True}


@router.post(
    "/{contract_id}/transition", response_model=ContractOut, dependencies=[Depends(require_manager)]
)
async def transition(
    contract_id: int,
    payload: StatusTransition,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.transition(tenant_id, user_id, contract_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ─── E-04 eSign ─────────────────────────────────────────
@router.get("/esign/mode")
async def esign_mode():
    """Devuelve el modo de eSign activo según las env vars."""
    return {"mode": esign_current_mode()}


@router.post(
    "/{contract_id}/esign/send",
    response_model=ESignResult,
    dependencies=[Depends(require_manager)],
)
async def send_for_signing(
    contract_id: int,
    payload: SendForSigning,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    try:
        return await service.send_for_signing(tenant_id, user_id, contract_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/{contract_id}/esign/mock-confirm",
    response_model=ContractOut,
)
async def mock_sign_confirm(
    contract_id: int,
    payload: MockSignConfirm,
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Endpoint público (auth básico via JWT) — el pad de firma del browser POST acá."""
    try:
        return await service.mock_sign_complete(tenant_id, contract_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/internal/esign/webhook")
async def docusign_webhook(
    payload: dict,
    service: ContractService = Depends(get_service),
):
    """DocuSign Connect llama acá cuando un envelope cambia de status. Sin auth (firma HMAC opcional)."""
    await service.docusign_webhook(payload)
    return {"ok": True}


# ─── Internal: cron de alertas (sin auth — solo invocable desde la red Docker) ─────────────────────────────────────────
# Gateway bloquea /internal/*. Si querés invocar desde un scheduler externo, usá /scan-expiry abajo.
@router.post("/internal/scan-expiry", response_model=ExpiryAlertResult)
async def internal_scan_expiry(
    tenant_id: int | None = Query(None),
    service: ContractService = Depends(get_service),
):
    return await service.scan_expiry(tenant_id)


# ─── Público: scan-expiry para el tenant del JWT (botón "Ejecutar scan" en UI) ─────────────────────────────────────────
@router.post("/scan-expiry", response_model=ExpiryAlertResult, dependencies=[Depends(require_admin)])
async def scan_expiry(
    service: ContractService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Recorre contratos del tenant actual y emite alertas de vencimiento. Solo admin."""
    return await service.scan_expiry(tenant_id)

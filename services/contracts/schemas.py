"""Contracts service — Pydantic schemas (E-02)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ContractIn(BaseModel):
    employee_id: int
    counterparty: str | None = None
    title: str = Field(min_length=1, max_length=256)
    contract_type: str = "general"
    body_md: str | None = None
    starts_on: date | None = None
    expires_on: date | None = None
    meta: dict | None = None


class ContractUpdate(BaseModel):
    counterparty: str | None = None
    title: str | None = None
    contract_type: str | None = None
    body_md: str | None = None
    starts_on: date | None = None
    expires_on: date | None = None
    meta: dict | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    employee_id: int
    counterparty: str | None
    title: str
    contract_type: str
    status: str
    body_md: str | None
    body_html: str | None
    source: str
    generated_doc_id: int | None
    starts_on: date | None
    expires_on: date | None
    signed_on: date | None
    meta: dict | None
    source_documents: list[dict] = Field(default_factory=list)
    # E-04: eSign
    esign_provider: str | None = None
    esign_envelope_id: str | None = None
    esign_status: str | None = None
    esign_signing_url: str | None = None
    esign_sent_at: datetime | None = None
    esign_completed_at: datetime | None = None
    esign_signer_email: str | None = None
    days_to_expiry: int | None = None
    created_at: datetime
    updated_at: datetime


class ContractSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    counterparty: str | None
    title: str
    contract_type: str
    status: str
    expires_on: date | None
    days_to_expiry: int | None = None
    source: str
    created_at: datetime


class StatusTransition(BaseModel):
    to_status: str  # review|signed|expired|cancelled|draft
    note: str | None = None
    signed_on: date | None = None  # solo aplica a signed


class ContractEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    from_status: str | None
    to_status: str | None
    note: str | None
    actor_user_id: int | None
    created_at: datetime


class ContractFromDocgen(BaseModel):
    """Persistir un GeneratedDoc como contrato — bridge AI-03 → E-02."""

    generated_doc_id: int
    employee_id: int
    contract_type: str = "general"
    counterparty: str | None = None
    starts_on: date | None = None
    expires_on: date | None = None
    meta: dict | None = None


class GenerateContractRequest(BaseModel):
    """E-03: corre DocGen internamente y persiste como contrato en una operación."""

    template_id: int
    employee_id: int
    contract_type: str = "general"
    counterparty: str | None = None
    starts_on: date | None = None
    expires_on: date | None = None
    custom_context: dict = Field(default_factory=dict)
    title_override: str | None = None


class ExpiryAlertResult(BaseModel):
    scanned: int
    contracts_alerted: int
    notifications_sent: int


# ─── E-04 eSign ────────────────────────────────────────
class SendForSigning(BaseModel):
    signer_email: str = Field(min_length=3, max_length=256)
    signer_name: str = Field(min_length=1, max_length=256)
    return_url: str | None = None  # URL a la que DocuSign redirige tras firmar


class ESignResult(BaseModel):
    envelope_id: str
    signing_url: str
    provider: str
    status: str


class MockSignConfirm(BaseModel):
    """El frontend del pad de firma confirma con esta payload."""

    envelope_id: str
    signature_data_url: str | None = None  # canvas → base64 PNG

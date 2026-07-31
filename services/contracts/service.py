"""Contracts service — business logic (E-02)."""

import logging
from datetime import date

import bleach
import httpx
import markdown as md
from sqlalchemy import text

from shared.config import get_settings
from shared.notifications import emit_notification
from services.contracts.models import Contract
from services.contracts.repository import ContractRepository
from services.contracts.esign import create_envelope, current_mode
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

logger = logging.getLogger(__name__)

# Estados permitidos y transiciones legales
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"review", "cancelled"},
    "review": {"signed", "draft", "cancelled"},
    "signed": {"expired", "cancelled"},
    "expired": set(),
    "cancelled": set(),
}

# Bleach allowlist (igual a docgen — coherencia visual)
ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "p", "br", "hr", "ul", "ol", "li",
    "strong", "em", "code", "pre", "blockquote", "table", "thead", "tbody", "tr", "td", "th",
]
ALLOWED_ATTRS = {"*": ["class"]}


def _render_html(body_md: str) -> str:
    html = md.markdown(body_md, extensions=["extra", "sane_lists", "smarty"])
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def _days_to_expiry(c: Contract) -> int | None:
    if not c.expires_on:
        return None
    return (c.expires_on - date.today()).days


def _to_summary(c: Contract) -> ContractSummary:
    base = ContractSummary.model_validate(c).model_dump()
    base["days_to_expiry"] = _days_to_expiry(c)
    return ContractSummary(**base)


def _to_full(c: Contract) -> ContractOut:
    base = ContractOut.model_validate(c).model_dump()
    base["days_to_expiry"] = _days_to_expiry(c)
    return ContractOut(**base)


class ContractService:
    def __init__(self, repo: ContractRepository):
        self.repo = repo

    # ─── CRUD ─────────────────────────────────────────
    async def list_contracts(
        self, tenant_id: int, status: str | None = None, employee_id: int | None = None
    ) -> list[ContractSummary]:
        rows = await self.repo.list_contracts(tenant_id, status, employee_id)
        return [_to_summary(c) for c in rows]

    async def get_contract(self, tenant_id: int, contract_id: int) -> ContractOut | None:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            return None
        return _to_full(c)

    async def list_events(self, tenant_id: int, contract_id: int) -> list[ContractEventOut]:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            raise ValueError("Contrato no encontrado")
        events = await self.repo.list_events(contract_id)
        return [ContractEventOut.model_validate(e) for e in events]

    async def create(
        self, tenant_id: int, user_id: int | None, payload: ContractIn
    ) -> ContractOut:
        data = payload.model_dump()
        data["tenant_id"] = tenant_id
        data["created_by"] = user_id
        if data.get("body_md"):
            data["body_html"] = _render_html(data["body_md"])
        contract = await self.repo.create(**data)
        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=contract.id, kind="status_change",
            from_status=None, to_status="draft", actor_user_id=user_id, note="Contrato creado",
        )
        return _to_full(contract)

    async def update(
        self, tenant_id: int, contract_id: int, payload: ContractUpdate
    ) -> ContractOut | None:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            return None
        if c.status in ("signed", "expired", "cancelled"):
            raise ValueError(f"No se puede editar un contrato en estado {c.status}")
        data = payload.model_dump(exclude_unset=True)
        if data.get("body_md"):
            data["body_html"] = _render_html(data["body_md"])
        await self.repo.update(c, **data)
        return _to_full(c)

    async def delete(self, tenant_id: int, contract_id: int) -> bool:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            return False
        if c.status == "signed":
            raise ValueError("No se puede eliminar un contrato firmado — usá 'cancelar' primero")
        await self.repo.delete(c)
        return True

    # ─── State machine ─────────────────────────────────────────
    async def transition(
        self, tenant_id: int, user_id: int | None, contract_id: int, t: StatusTransition
    ) -> ContractOut:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            raise ValueError("Contrato no encontrado")
        allowed = ALLOWED_TRANSITIONS.get(c.status, set())
        if t.to_status not in allowed:
            raise ValueError(
                f"Transición ilegal: {c.status} → {t.to_status}. "
                f"Permitidas desde {c.status}: {sorted(allowed) or ['(ninguna)']}"
            )
        old_status = c.status
        try:
            from shared.metrics import CONTRACTS_TRANSITIONS
            CONTRACTS_TRANSITIONS.labels(from_status=old_status, to_status=t.to_status).inc()
        except Exception:  # noqa: BLE001
            pass
        update_data: dict = {"status": t.to_status}
        if t.to_status == "signed":
            update_data["signed_on"] = t.signed_on or date.today()
            # Limpiar alertas previas (puede volver a notificar nuevas si la firma extiende vencimiento)
            update_data["alerts_sent"] = []
        await self.repo.update(c, **update_data)
        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=c.id, kind="status_change",
            from_status=old_status, to_status=t.to_status,
            actor_user_id=user_id, note=t.note,
        )

        # Notificación al empleado en transiciones relevantes
        if t.to_status in ("signed", "expired", "cancelled"):
            await self._notify_status(tenant_id, c, t.to_status)

        # Emitir evento a n8n (best-effort, no rompe si falla)
        try:
            from shared.n8n_client import emit_event
            await emit_event(f"xtask.contract.{t.to_status}", {
                "tenant_id": tenant_id,
                "contract_id": c.id,
                "title": c.title,
                "counterparty": c.counterparty,
                "employee_id": c.employee_id,
                "from_status": old_status,
                "to_status": t.to_status,
            })
        except Exception:  # noqa: BLE001
            pass

        return _to_full(c)

    async def _notify_status(self, tenant_id: int, c: Contract, status: str) -> None:
        try:
            user_id, _ = await self.repo.get_employee_user(tenant_id, c.employee_id)
            if not user_id:
                return
            titles = {
                "signed": f'Contrato "{c.title}" firmado',
                "expired": f'Contrato "{c.title}" vencido',
                "cancelled": f'Contrato "{c.title}" cancelado',
            }
            kinds = {"signed": "success", "expired": "warning", "cancelled": "info"}
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id,
                user_id=user_id,
                title=titles.get(status, f"Contrato actualizado: {status}"),
                body=f"Estado actualizado en {date.today().isoformat()}.",
                kind=kinds.get(status, "info"),
                category="contracts",
                action_url=f"/contratos/{c.id}",
                meta={"contract_id": c.id, "status": status},
                email=(status == "signed"),  # P-04.2: solo enviamos email al firmar
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("contract_status_notif_failed", exc_info=e)

    # ─── E-03: Generación end-to-end DocGen+RAG → Contrato ─────────────────────────────────────────
    async def generate_contract(
        self, tenant_id: int, user_id: int | None, payload: GenerateContractRequest
    ) -> ContractOut:
        """Llama internamente a DocGen, lo persiste, luego crea el contrato con trazabilidad.

        Flujo:
          1. POST docgen/internal/generate → GeneratedDoc con citas del RAG.
          2. Crear Contract con body copiado + source_documents = citas del paso 1.
          3. Audit event.
        """
        settings = get_settings()
        url = f"{settings.DOCGEN_SERVICE_URL}/api/docgen/internal/generate"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    url,
                    params={"tenant_id": tenant_id, "user_id": user_id} if user_id else {"tenant_id": tenant_id},
                    json={
                        "template_id": payload.template_id,
                        "employee_id": payload.employee_id,
                        "custom_context": payload.custom_context or {},
                        "title": payload.title_override,
                    },
                )
                if resp.status_code != 200:
                    detail = resp.text
                    try:
                        detail = resp.json().get("detail", detail)
                    except Exception:  # noqa: BLE001
                        pass
                    raise ValueError(f"DocGen falló: {detail}")
                gen = resp.json()
        except httpx.RequestError as e:
            raise ValueError(f"No se pudo conectar al servicio DocGen: {e}") from e

        contract = await self.repo.create(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            counterparty=payload.counterparty,
            title=gen["title"],
            contract_type=payload.contract_type,
            body_md=gen.get("body_md"),
            body_html=gen.get("body_html"),
            source="docgen",
            generated_doc_id=gen["id"],
            starts_on=payload.starts_on,
            expires_on=payload.expires_on,
            meta=None,
            source_documents=gen.get("citations") or [],
            created_by=user_id,
        )
        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=contract.id, kind="status_change",
            from_status=None, to_status="draft", actor_user_id=user_id,
            note=f"Generado desde plantilla #{payload.template_id} con {len(gen.get('citations') or [])} citas del corpus",
        )
        return _to_full(contract)

    # ─── Bridge desde DocGen ─────────────────────────────────────────
    async def create_from_docgen(
        self, tenant_id: int, user_id: int | None, payload: ContractFromDocgen
    ) -> ContractOut:
        # Buscar el GeneratedDoc para copiar body
        row = (
            await self.repo.db.execute(
                text(
                    "SELECT title, body_md, body_html FROM svc_docgen.generated_docs "
                    "WHERE id = :did AND tenant_id = :tid LIMIT 1"
                ),
                {"did": payload.generated_doc_id, "tid": tenant_id},
            )
        ).first()
        if not row:
            raise ValueError("GeneratedDoc no encontrado en este tenant")

        contract = await self.repo.create(
            tenant_id=tenant_id,
            employee_id=payload.employee_id,
            counterparty=payload.counterparty,
            title=str(row[0]),
            contract_type=payload.contract_type,
            body_md=str(row[1]) if row[1] else None,
            body_html=str(row[2]) if row[2] else None,
            source="docgen",
            generated_doc_id=payload.generated_doc_id,
            starts_on=payload.starts_on,
            expires_on=payload.expires_on,
            meta=payload.meta,
            created_by=user_id,
        )
        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=contract.id, kind="status_change",
            from_status=None, to_status="draft", actor_user_id=user_id,
            note=f"Generado desde plantilla (doc #{payload.generated_doc_id})",
        )
        return _to_full(contract)

    # ─── E-04 eSign ─────────────────────────────────────────
    async def send_for_signing(
        self, tenant_id: int, user_id: int | None, contract_id: int, payload: SendForSigning
    ) -> ESignResult:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            raise ValueError("Contrato no encontrado")
        if c.status not in ("draft", "review"):
            raise ValueError(f"Solo se envían contratos en draft o review (actual: {c.status})")
        if c.esign_envelope_id:
            raise ValueError("Este contrato ya tiene un envelope abierto")

        env = await create_envelope(
            contract_id=c.id,
            contract_title=c.title,
            contract_html=c.body_html or "<p>(sin contenido)</p>",
            signer_email=payload.signer_email,
            signer_name=payload.signer_name,
            return_url=payload.return_url or f"http://localhost:3001/contratos/{c.id}",
        )

        await self.repo.update(
            c,
            esign_provider=env.provider,
            esign_envelope_id=env.envelope_id,
            esign_status=env.status,
            esign_signing_url=env.signing_url,
            esign_sent_at=datetime.utcnow(),
            esign_signer_email=payload.signer_email,
            status="review",  # auto-mueve a review al enviar
        )
        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=c.id, kind="status_change",
            from_status="draft", to_status="review", actor_user_id=user_id,
            note=f"Enviado a firma vía {env.provider} · envelope {env.envelope_id}",
        )
        return ESignResult(
            envelope_id=env.envelope_id, signing_url=env.signing_url,
            provider=env.provider, status=env.status,
        )

    async def mock_sign_complete(
        self, tenant_id: int, contract_id: int, payload: MockSignConfirm,
    ) -> ContractOut:
        c = await self.repo.get_contract(tenant_id, contract_id)
        if not c:
            raise ValueError("Contrato no encontrado")
        if c.esign_provider != "mock":
            raise ValueError("Este contrato no es mock-sign")
        if c.esign_envelope_id != payload.envelope_id:
            raise ValueError("Envelope ID no coincide")

        await self.repo.update(
            c,
            esign_status="completed",
            esign_completed_at=datetime.utcnow(),
            status="signed",
            signed_on=date.today(),
            alerts_sent=[],
        )
        # Guardamos la firma como imagen base64 en meta para auditoría
        if payload.signature_data_url:
            new_meta = dict(c.meta or {})
            new_meta["mock_signature"] = payload.signature_data_url[:5000]
            new_meta["mock_signed_at"] = datetime.utcnow().isoformat()
            await self.repo.update(c, meta=new_meta)

        await self.repo.add_event(
            tenant_id=tenant_id, contract_id=c.id, kind="status_change",
            from_status="review", to_status="signed",
            note="Firmado vía mock signature pad",
        )
        await self._notify_status(tenant_id, c, "signed")
        return _to_full(c)

    async def docusign_webhook(self, payload: dict) -> None:
        """Recibe el callback de DocuSign (Connect) cuando el status cambia."""
        envelope_id = payload.get("data", {}).get("envelopeId") or payload.get("envelopeId")
        status = payload.get("data", {}).get("envelopeSummary", {}).get("status") or payload.get("status")
        if not envelope_id or not status:
            logger.warning("docusign_webhook_missing_data", payload=str(payload)[:200])
            return

        # Buscamos el contract por envelope_id (cross-tenant porque el webhook no trae tenant)
        from sqlalchemy import select
        from services.contracts.models import Contract
        stmt = select(Contract).where(Contract.esign_envelope_id == envelope_id)
        c = (await self.repo.db.execute(stmt)).scalar_one_or_none()
        if not c:
            logger.warning("docusign_webhook_envelope_not_found", env=envelope_id)
            return

        await self.repo.update(c, esign_status=status)
        if status.lower() == "completed":
            await self.repo.update(
                c, status="signed", signed_on=date.today(),
                esign_completed_at=datetime.utcnow(), alerts_sent=[],
            )
            await self.repo.add_event(
                tenant_id=c.tenant_id, contract_id=c.id, kind="status_change",
                from_status="review", to_status="signed",
                note=f"Firmado vía DocuSign · envelope {envelope_id}",
            )
            await self._notify_status(c.tenant_id, c, "signed")

    # ─── Alertas de vencimiento (60/30/15 días) ─────────────────────────────────────────
    async def scan_expiry(self, tenant_id: int | None = None) -> ExpiryAlertResult:
        """Recorre contratos activos y emite alertas según ventanas 60/30/15.

        Cron diario invocará este endpoint. Si tenant_id es None, escanea todos.
        """
        today = date.today()
        thresholds = [60, 30, 15]

        # Filtramos por tenant si vino
        rows = await self.repo.find_expiring(today, max_days_ahead=60)
        if tenant_id is not None:
            rows = [c for c in rows if c.tenant_id == tenant_id]

        alerted = 0
        notif_count = 0
        for c in rows:
            days = (c.expires_on - today).days if c.expires_on else None
            if days is None:
                continue
            sent_keys = c.alerts_sent or []
            for th in thresholds:
                # Notificamos cuando faltan ≤ th días Y no se notificó esa ventana
                if days <= th and f"d{th}" not in sent_keys:
                    user_id, name = await self.repo.get_employee_user(c.tenant_id, c.employee_id)
                    if user_id:
                        try:
                            await emit_notification(
                                self.repo.db,
                                tenant_id=c.tenant_id,
                                user_id=user_id,
                                title=f'Contrato "{c.title}" vence en {days} día{"s" if days != 1 else ""}',
                                body=f"Recordatorio automático para {name}. Revisá la renovación o firma.",
                                kind="warning" if days > 15 else "error",
                                category="contracts",
                                action_url=f"/contratos/{c.id}",
                                meta={"contract_id": c.id, "days_to_expiry": days, "threshold": th},
                            )
                            notif_count += 1
                        except Exception as e:  # noqa: BLE001
                            logger.warning("expiry_notif_failed", exc_info=e)
                    await self.repo.mark_alert_sent(c.id, f"d{th}")
                    await self.repo.add_event(
                        tenant_id=c.tenant_id, contract_id=c.id, kind="alert",
                        note=f"Alerta vencimiento {th}d (faltan {days})",
                    )
                    alerted += 1
                    break  # un solo umbral por ronda
        return ExpiryAlertResult(
            scanned=len(rows), contracts_alerted=alerted, notifications_sent=notif_count
        )

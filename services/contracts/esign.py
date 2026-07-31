"""eSign client (E-04).

Modos:
- docusign: integración real vía DocuSign eSignature REST API v2.1.
  Requiere DOCUSIGN_INTEGRATOR_KEY, DOCUSIGN_USER_ID, DOCUSIGN_ACCOUNT_ID y
  DOCUSIGN_RSA_PRIVATE_KEY en env. Usa JWT grant.
- mock: simula el flujo sin llamar a DocuSign. Genera un envelope_id pseudo y
  un signing_url interno (/contratos/{id}/mock-sign) que el frontend renderiza
  como un pad de firma. Útil para demo y desarrollo sin cuenta DocuSign.

Selección: si las 4 env vars existen, modo docusign. Sino, mock.
"""

import base64
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

ESignMode = Literal["docusign", "mock"]


@dataclass(frozen=True)
class EnvelopeCreated:
    envelope_id: str
    signing_url: str
    provider: ESignMode
    status: str


def _has_docusign_config() -> bool:
    return all(
        os.getenv(k)
        for k in (
            "DOCUSIGN_INTEGRATOR_KEY",
            "DOCUSIGN_USER_ID",
            "DOCUSIGN_ACCOUNT_ID",
            "DOCUSIGN_RSA_PRIVATE_KEY",
        )
    )


def current_mode() -> ESignMode:
    return "docusign" if _has_docusign_config() else "mock"


async def create_envelope(
    *,
    contract_id: int,
    contract_title: str,
    contract_html: str,
    signer_email: str,
    signer_name: str,
    return_url: str,
) -> EnvelopeCreated:
    """Crea un envelope para firmar el contract.

    Retorna envelope_id + signing_url. El signing_url se le abre al firmante
    en una pestaña nueva.
    """
    if current_mode() == "docusign":
        return await _docusign_create_envelope(
            contract_id=contract_id, contract_title=contract_title,
            contract_html=contract_html, signer_email=signer_email,
            signer_name=signer_name, return_url=return_url,
        )
    return _mock_create_envelope(contract_id=contract_id)


def _mock_create_envelope(contract_id: int) -> EnvelopeCreated:
    """Genera un envelope_id + signing_url que apunta al pad de firma interno."""
    env_id = f"mock-{uuid.uuid4().hex[:16]}"
    # El frontend muestra una página /contratos/{id}/mock-sign con un canvas
    # donde el usuario dibuja la firma y al confirmar marca el contrato como signed.
    return EnvelopeCreated(
        envelope_id=env_id,
        signing_url=f"/contratos/{contract_id}/mock-sign?envelope={env_id}",
        provider="mock", status="sent",
    )


async def _docusign_create_envelope(
    *, contract_id: int, contract_title: str, contract_html: str,
    signer_email: str, signer_name: str, return_url: str,
) -> EnvelopeCreated:
    """Crea un envelope real en DocuSign.

    Flow JWT:
    1. Obtener access_token con JWT grant.
    2. POST /accounts/{account_id}/envelopes con el documento HTML.
    3. POST /accounts/{account_id}/envelopes/{id}/views/recipient para signing_url embebido.
    """
    token = await _docusign_jwt_token()
    account_id = os.environ["DOCUSIGN_ACCOUNT_ID"]
    base_url = os.getenv("DOCUSIGN_API_BASE", "https://demo.docusign.net/restapi")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Doc en base64
    doc_b64 = base64.b64encode(contract_html.encode("utf-8")).decode()

    payload = {
        "emailSubject": f"Firmá: {contract_title}",
        "status": "sent",
        "documents": [{
            "documentBase64": doc_b64,
            "name": contract_title,
            "fileExtension": "html",
            "documentId": "1",
        }],
        "recipients": {
            "signers": [{
                "email": signer_email,
                "name": signer_name,
                "recipientId": "1",
                "clientUserId": str(contract_id),
                "tabs": {
                    "signHereTabs": [{
                        "documentId": "1", "pageNumber": "1",
                        "xPosition": "100", "yPosition": "700",
                    }],
                },
            }],
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as c:
        resp = await c.post(
            f"{base_url}/v2.1/accounts/{account_id}/envelopes",
            json=payload, headers=headers,
        )
        resp.raise_for_status()
        env = resp.json()
        envelope_id = env["envelopeId"]

        view_resp = await c.post(
            f"{base_url}/v2.1/accounts/{account_id}/envelopes/{envelope_id}/views/recipient",
            json={
                "returnUrl": return_url,
                "authenticationMethod": "none",
                "email": signer_email,
                "userName": signer_name,
                "recipientId": "1",
                "clientUserId": str(contract_id),
            },
            headers=headers,
        )
        view_resp.raise_for_status()
        signing_url = view_resp.json()["url"]

    return EnvelopeCreated(
        envelope_id=envelope_id, signing_url=signing_url,
        provider="docusign", status="sent",
    )


async def _docusign_jwt_token() -> str:
    """Obtiene un access_token via JWT grant (requiere consentimiento previo)."""
    from jose import jwt  # python-jose ya está en deps
    import time

    integrator_key = os.environ["DOCUSIGN_INTEGRATOR_KEY"]
    user_id = os.environ["DOCUSIGN_USER_ID"]
    private_key = os.environ["DOCUSIGN_RSA_PRIVATE_KEY"]
    aud = os.getenv("DOCUSIGN_AUTH_HOST", "account-d.docusign.com")

    now = int(time.time())
    claims = {
        "iss": integrator_key, "sub": user_id, "aud": aud,
        "iat": now, "exp": now + 3600,
        "scope": "signature impersonation",
    }
    assertion = jwt.encode(claims, private_key, algorithm="RS256")

    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.post(
            f"https://{aud}/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def fetch_envelope_status(envelope_id: str) -> str | None:
    """Polling de status (no usado por default; el webhook empuja cambios)."""
    if envelope_id.startswith("mock-"):
        return None
    if not _has_docusign_config():
        return None
    try:
        token = await _docusign_jwt_token()
        account_id = os.environ["DOCUSIGN_ACCOUNT_ID"]
        base_url = os.getenv("DOCUSIGN_API_BASE", "https://demo.docusign.net/restapi")
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                f"{base_url}/v2.1/accounts/{account_id}/envelopes/{envelope_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            r.raise_for_status()
            return r.json().get("status")
    except Exception as e:  # noqa: BLE001
        logger.warning("docusign_status_fetch_failed", exc_info=e)
        return None

"""Cliente para emitir eventos a n8n vía webhooks.

Patrón de uso
-------------
Desde cualquier service, llamar:

    from shared.n8n_client import emit_event
    await emit_event("xtask.contract.signed", {"contract_id": 123, "tenant_id": 2})

n8n recibe esto en su webhook `/webhook/xtask-events` (o el path configurado)
y dispara el workflow correspondiente con un Switch node por `event_name`.

Best-effort
-----------
- Si n8n está down, fallamos silenciosamente y registramos warning. NUNCA
  rompemos la operación principal (firma de contrato, alta de empleado…)
  por un fallo en una integración.
- Timeout corto (3s) para no bloquear el flow.
- Concurrencia: usamos un httpx.AsyncClient único cached por proceso.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE = "http://n8n:5678"
_DEFAULT_PATH = "/webhook/xtask-events"
_DEFAULT_TIMEOUT = 3.0

_client: httpx.AsyncClient | None = None


def _base_url() -> str:
    return os.environ.get("N8N_WEBHOOK_BASE", _DEFAULT_BASE).rstrip("/")


def _webhook_path() -> str:
    return os.environ.get("N8N_WEBHOOK_PATH", _DEFAULT_PATH)


def _enabled() -> bool:
    """n8n integration is opt-in via env flag — off by default in tests."""
    return os.environ.get("N8N_ENABLED", "true").lower() in ("1", "true", "yes")


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
    return _client


async def emit_event(event_name: str, payload: dict[str, Any]) -> bool:
    """Emit an event to n8n. Returns True on success, False on failure.

    Failures are logged but never raised — integrations are best-effort.
    """
    if not _enabled():
        return False

    url = f"{_base_url()}{_webhook_path()}"
    body = {"event": event_name, **payload}
    try:
        resp = await _get_client().post(url, json=body)
        if resp.status_code >= 400:
            logger.warning(
                "n8n webhook returned %s for event=%s",
                resp.status_code, event_name,
            )
            return False
        return True
    except (httpx.RequestError, httpx.HTTPError) as exc:
        # n8n unreachable, workflow not configured for this event, etc.
        logger.debug("n8n event '%s' failed: %s", event_name, exc)
        return False

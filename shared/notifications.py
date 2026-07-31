"""Helper para emitir notificaciones in-app desde cualquier servicio.

Diseño:
- Cada microservicio tiene acceso a la misma DB Postgres (multi-schema).
- Insertamos directamente en svc_notifications.notifications via SQL raw para
  evitar acoplamiento de modelos entre servicios.
- Es fire-and-forget: si falla, logueamos pero no rompemos el flujo original.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger

logger = get_logger(__name__)


async def emit_notification(
    db: AsyncSession,
    *,
    tenant_id: int | None,
    user_id: int | None,
    title: str,
    body: str | None = None,
    kind: str = "info",                  # info | success | warning | error
    category: str = "general",
    action_url: str | None = None,
    meta: dict | None = None,
    email: bool = False,                 # P-04.2: si true, también dispara email
) -> None:
    """Emite una notificación. Tolera fallos silenciosamente.

    Si tenant_id o user_id son None, no hace nada (no hay a quién mandar)."""
    if tenant_id is None or user_id is None:
        return
    try:
        await db.execute(
            text("""
                INSERT INTO svc_notifications.notifications
                    (tenant_id, user_id, kind, category, title, body, action_url, meta, archived, created_at)
                VALUES
                    (:tenant_id, :user_id, :kind, :category, :title, :body, :action_url,
                     CAST(:meta AS JSON), false, NOW())
            """),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "kind": kind,
                "category": category,
                "title": title,
                "body": body,
                "action_url": action_url,
                "meta": __json_dumps(meta or {}),
            },
        )
        # Sprint 7: contador Prometheus (no rompe si prometheus_client no está instalado)
        try:
            from shared.metrics import NOTIFICATIONS_EMITTED
            NOTIFICATIONS_EMITTED.labels(kind=kind, category=category).inc()
        except Exception:  # noqa: BLE001
            pass

        # P-04.2: dispatch email si el caller lo pidió y el usuario tiene email habilitado
        if email:
            await _dispatch_email_async(
                db, tenant_id=tenant_id, user_id=user_id, title=title,
                body=body or "", category=category, action_url=action_url,
            )
    except Exception as e:  # noqa: BLE001
        logger.warning("notification_emit_failed", error=str(e), title=title, user_id=user_id, tenant_id=tenant_id)


async def _dispatch_email_async(
    db: AsyncSession,
    *,
    tenant_id: int,
    user_id: int,
    title: str,
    body: str,
    category: str,
    action_url: str | None,
) -> None:
    """Resuelve email del usuario, chequea preferencias y dispara email_client.send."""
    try:
        # 1) Pref del usuario
        pref = (await db.execute(
            text(
                "SELECT email_enabled, category_overrides FROM svc_notifications.user_preferences "
                "WHERE user_id = :uid LIMIT 1"
            ),
            {"uid": user_id},
        )).first()
        if pref:
            email_enabled = bool(pref[0])
            overrides = pref[1] or {}
            if not email_enabled:
                return
            if category in overrides and overrides[category] is False:
                return

        # 2) Email del usuario
        urow = (await db.execute(
            text("SELECT email FROM svc_auth.users WHERE id = :uid LIMIT 1"),
            {"uid": user_id},
        )).first()
        if not urow or not urow[0]:
            return
        to_email = str(urow[0])

        # 3) Render y send
        try:
            from services.notifications.email_client import send_email
            from services.notifications.email_templates import render_email
        except Exception:  # noqa: BLE001
            return  # módulos no disponibles (servicio que no es notifications)

        cta_url = None
        if action_url:
            base = "http://localhost:3001"
            cta_url = action_url if action_url.startswith("http") else f"{base}{action_url}"
        html, text_body = render_email(
            title=title, body=f"<p>{body}</p>", cta_label="Abrir en XTask" if cta_url else None,
            cta_url=cta_url, category=category,
        )
        result = await send_email(to=to_email, subject=title, html=html, text=text_body)

        # 4) Marcar en la última notif insertada (no esencial pero útil para debug)
        try:
            await db.execute(
                text(
                    "UPDATE svc_notifications.notifications "
                    "SET email_status = :st, email_sent_at = NOW(), email_error = :err "
                    "WHERE tenant_id = :tid AND user_id = :uid AND title = :title "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {
                    "st": result.get("status"),
                    "err": None if result.get("status") == "sent" else result.get("detail", ""),
                    "tid": tenant_id, "uid": user_id, "title": title,
                },
            )
        except Exception:  # noqa: BLE001
            pass  # postgres no soporta ORDER BY/LIMIT en UPDATE — silencio si falla
    except Exception as e:  # noqa: BLE001
        logger.warning("email_dispatch_failed", exc_info=e)


async def emit_to_many(
    db: AsyncSession,
    *,
    tenant_id: int | None,
    user_ids: Iterable[int],
    **kwargs,
) -> None:
    """Atajo para emitir la misma notif a una lista de usuarios."""
    for uid in user_ids:
        await emit_notification(db, tenant_id=tenant_id, user_id=uid, **kwargs)


def __json_dumps(d: dict) -> str:
    import json
    return json.dumps(d, default=str)

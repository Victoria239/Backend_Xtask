"""Notifications service - HTTP routes (P-04 in-app channel)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_tenant_id, get_current_user_id, require_admin
from services.notifications.email_client import current_mode as email_mode, send_email
from services.notifications.email_templates import render_email
from services.notifications.repository import NotificationRepository
from services.notifications.schemas import (
    MarkReadRequest,
    NotificationCreate,
    NotificationOut,
    UnreadCount,
)
from services.notifications.service import NotificationService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_service_db("notifications"))) -> NotificationService:
    return NotificationService(NotificationRepository(db))


# ─── P-04.2 Email preferences ───────────────────────────
class PreferencesOut(BaseModel):
    email_enabled: bool
    category_overrides: dict


class PreferencesUpdate(BaseModel):
    email_enabled: bool | None = None
    category_overrides: dict | None = None


class TestEmailRequest(BaseModel):
    to: str
    subject: str = "Test desde XTask"
    body: str = "Esto es un email de prueba enviado desde el panel de configuración."


@router.get("/email/mode")
async def get_email_mode():
    return {"mode": email_mode()}


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(
    db: AsyncSession = Depends(get_service_db("notifications")),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    row = (await db.execute(
        text(
            "SELECT email_enabled, category_overrides FROM svc_notifications.user_preferences "
            "WHERE user_id = :uid LIMIT 1"
        ),
        {"uid": user_id},
    )).first()
    if not row:
        return PreferencesOut(email_enabled=True, category_overrides={})
    return PreferencesOut(
        email_enabled=bool(row[0]), category_overrides=row[1] or {},
    )


@router.put("/preferences", response_model=PreferencesOut)
async def update_preferences(
    payload: PreferencesUpdate,
    db: AsyncSession = Depends(get_service_db("notifications")),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    # Upsert simple
    import json
    existing = (await db.execute(
        text("SELECT id, email_enabled, category_overrides FROM svc_notifications.user_preferences WHERE user_id = :uid"),
        {"uid": user_id},
    )).first()
    if existing:
        new_email_enabled = payload.email_enabled if payload.email_enabled is not None else bool(existing[1])
        new_overrides = payload.category_overrides if payload.category_overrides is not None else (existing[2] or {})
        await db.execute(
            text(
                "UPDATE svc_notifications.user_preferences "
                "SET email_enabled = :en, category_overrides = CAST(:co AS JSON), updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"en": new_email_enabled, "co": json.dumps(new_overrides), "id": existing[0]},
        )
    else:
        new_email_enabled = payload.email_enabled if payload.email_enabled is not None else True
        new_overrides = payload.category_overrides if payload.category_overrides is not None else {}
        await db.execute(
            text(
                "INSERT INTO svc_notifications.user_preferences (tenant_id, user_id, email_enabled, category_overrides) "
                "VALUES (:tid, :uid, :en, CAST(:co AS JSON))"
            ),
            {"tid": tenant_id, "uid": user_id, "en": new_email_enabled, "co": json.dumps(new_overrides)},
        )
    return PreferencesOut(email_enabled=new_email_enabled, category_overrides=new_overrides)


@router.post("/email/test")
async def test_email(
    payload: TestEmailRequest,
    db: AsyncSession = Depends(get_service_db("notifications")),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    """Dispara un email de prueba (sin guardar como notificación)."""
    html, text_body = render_email(
        title=payload.subject, body=f"<p>{payload.body}</p>",
        cta_label="Volver a XTask", cta_url="http://localhost:3001/",
        category="general",
    )
    result = await send_email(to=payload.to, subject=payload.subject, html=html, text=text_body)
    return result


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    unread_only: bool = Query(False),
    service: NotificationService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    return await service.list_for_user(tenant_id, user_id, unread_only=unread_only)


@router.get("/count", response_model=UnreadCount)
async def count_unread(
    service: NotificationService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    unread, total = await service.unread_count(tenant_id, user_id)
    return UnreadCount(unread=unread, total=total)


@router.post("/mark-read", response_model=UnreadCount)
async def mark_read(
    payload: MarkReadRequest,
    service: NotificationService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    await service.mark_read(tenant_id, user_id, payload.ids)
    unread, total = await service.unread_count(tenant_id, user_id)
    return UnreadCount(unread=unread, total=total)


@router.delete("/{notif_id}", status_code=204)
async def archive_notification(
    notif_id: int,
    service: NotificationService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
    user_id: int = Depends(get_current_user_id),
):
    ok = await service.archive(tenant_id, user_id, notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")


# ─── Admin-only: crear notificaciones manualmente (para debug/demo) ──────
@router.post("", response_model=NotificationOut, dependencies=[Depends(require_admin)])
async def create_notification(
    payload: NotificationCreate,
    service: NotificationService = Depends(get_service),
    tenant_id: int = Depends(get_current_tenant_id),
):
    notif = await service.emit(
        tenant_id=tenant_id,
        user_id=payload.user_id,
        title=payload.title,
        body=payload.body,
        kind=payload.kind,
        category=payload.category,
        action_url=payload.action_url,
        meta=payload.meta,
    )
    return notif

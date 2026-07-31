"""Notifications service - SQLAlchemy models (P-04 in-app channel).

Multi-tenant aware: every notification is bound to (tenant_id, user_id).
Email/SMS channels se conectan en P-04 fase 2 vía un dispatcher.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Notification(Base):
    """Notificación in-app dirigida a un usuario específico dentro de un tenant.

    `kind` agrupa el estilo visual (info/success/warning/error).
    `category` agrupa por dominio (rag, kpis, payroll, etc) para filtrado UI.
    `action_url` es la ruta interna a la que el bell drop-down redirige al click.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_user_unread", "tenant_id", "user_id", "read_at"),
        Index("ix_notif_created", "tenant_id", "created_at"),
        {"schema": "svc_notifications"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="general")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=True)
    action_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # P-04.2: email channel
    email_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # null (in-app only) | queued | sent | failed | skipped
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserNotificationPreference(Base):
    """Preferencias por usuario: qué categorías quiere recibir por email."""

    __tablename__ = "user_preferences"
    __table_args__ = {"schema": "svc_notifications"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON con categorías: {"contracts": true, "leaves": false, ...}
    category_overrides: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""Notifications service - DB repository."""

from datetime import datetime

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.notifications.models import Notification


class NotificationRepository:
    model = Notification

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> Notification:
        notif = Notification(**data)
        self.db.add(notif)
        await self.db.flush()
        await self.db.refresh(notif)
        return notif

    async def list_for_user(
        self,
        tenant_id: int,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.archived.is_(False),
            )
            .order_by(desc(Notification.created_at))
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def count_unread(self, tenant_id: int, user_id: int) -> tuple[int, int]:
        """(unread, total) en una sola pasada — barato porque hay índice."""
        stmt_total = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.archived.is_(False),
            )
        )
        stmt_unread = stmt_total.where(Notification.read_at.is_(None))
        total = (await self.db.execute(stmt_total)).scalar_one()
        unread = (await self.db.execute(stmt_unread)).scalar_one()
        return int(unread), int(total)

    async def mark_read(
        self,
        tenant_id: int,
        user_id: int,
        ids: list[int] | None,
    ) -> int:
        """Si ids es None marca TODAS las del user. Devuelve cuántas afectó."""
        stmt = (
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.utcnow())
        )
        if ids:
            stmt = stmt.where(Notification.id.in_(ids))
        res = await self.db.execute(stmt)
        return res.rowcount or 0

    async def archive(self, tenant_id: int, user_id: int, notif_id: int) -> bool:
        stmt = (
            update(Notification)
            .where(
                Notification.id == notif_id,
                Notification.tenant_id == tenant_id,
                Notification.user_id == user_id,
            )
            .values(archived=True)
        )
        res = await self.db.execute(stmt)
        return (res.rowcount or 0) > 0

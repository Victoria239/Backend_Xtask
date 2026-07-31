"""Notifications service - business logic.

API thin layer sobre el repository. Validaciones de tenant ya están en
el router via dependencies.
"""

from services.notifications.models import Notification
from services.notifications.repository import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def emit(
        self,
        tenant_id: int,
        user_id: int,
        title: str,
        body: str | None = None,
        kind: str = "info",
        category: str = "general",
        action_url: str | None = None,
        meta: dict | None = None,
    ) -> Notification:
        """Crea una notificación. Llamable desde otros services internos."""
        return await self.repo.create({
            "tenant_id": tenant_id,
            "user_id": user_id,
            "title": title,
            "body": body,
            "kind": kind,
            "category": category,
            "action_url": action_url,
            "meta": meta or {},
        })

    async def list_for_user(self, tenant_id: int, user_id: int, unread_only: bool = False) -> list[Notification]:
        return await self.repo.list_for_user(tenant_id, user_id, unread_only=unread_only)

    async def unread_count(self, tenant_id: int, user_id: int) -> tuple[int, int]:
        return await self.repo.count_unread(tenant_id, user_id)

    async def mark_read(self, tenant_id: int, user_id: int, ids: list[int] | None) -> int:
        return await self.repo.mark_read(tenant_id, user_id, ids)

    async def archive(self, tenant_id: int, user_id: int, notif_id: int) -> bool:
        return await self.repo.archive(tenant_id, user_id, notif_id)

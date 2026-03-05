"""Decorator Pattern — Repository wrappers for cross-cutting concerns.

Wraps any BaseRepository to add caching, auditing, or retry logic
without modifying the original repository class.

Usage:
    base_repo = EmployeeRepository(db)
    repo = AuditedRepository(CachedRepository(base_repo))
    # repo.get_by_id() → checks cache → delegates to base → logs audit
"""

from typing import Any

from shared.logging import get_logger
from shared.events import event_bus

logger = get_logger(__name__)


class RepositoryDecorator:
    """Base decorator that delegates all calls to the wrapped repository."""

    def __init__(self, wrapped):
        self._wrapped = wrapped

    @property
    def db(self):
        return self._wrapped.db

    @property
    def model(self):
        return self._wrapped.model

    async def get_by_id(self, entity_id: int):
        return await self._wrapped.get_by_id(entity_id)

    async def get_all(self, filters=None, order_by="created_at", descending=True):
        return await self._wrapped.get_all(filters, order_by, descending)

    async def get_paginated(self, page=1, page_size=20, filters=None, order_by="created_at", descending=True):
        return await self._wrapped.get_paginated(page, page_size, filters, order_by, descending)

    async def create(self, data: dict[str, Any]):
        return await self._wrapped.create(data)

    async def update(self, entity_id: int, data: dict[str, Any]):
        return await self._wrapped.update(entity_id, data)

    async def delete(self, entity_id: int) -> bool:
        return await self._wrapped.delete(entity_id)

    def __getattr__(self, name):
        """Delegate any non-overridden attribute to the wrapped repo."""
        return getattr(self._wrapped, name)


class AuditedRepository(RepositoryDecorator):
    """Logs all write operations (create, update, delete) with structured logging."""

    def __init__(self, wrapped, actor_id: int | None = None):
        super().__init__(wrapped)
        self._actor_id = actor_id
        self._entity_name = wrapped.model.__tablename__

    async def create(self, data: dict[str, Any]):
        result = await self._wrapped.create(data)
        logger.info(
            "entity_created",
            entity=self._entity_name,
            entity_id=result.id,
            actor_id=self._actor_id,
        )
        await event_bus.emit(f"{self._entity_name}.created", {
            "entity_id": result.id,
            "actor_id": self._actor_id,
        })
        return result

    async def update(self, entity_id: int, data: dict[str, Any]):
        result = await self._wrapped.update(entity_id, data)
        if result:
            logger.info(
                "entity_updated",
                entity=self._entity_name,
                entity_id=entity_id,
                fields=list(data.keys()),
                actor_id=self._actor_id,
            )
            await event_bus.emit(f"{self._entity_name}.updated", {
                "entity_id": entity_id,
                "fields": list(data.keys()),
                "actor_id": self._actor_id,
            })
        return result

    async def delete(self, entity_id: int) -> bool:
        deleted = await self._wrapped.delete(entity_id)
        if deleted:
            logger.info(
                "entity_deleted",
                entity=self._entity_name,
                entity_id=entity_id,
                actor_id=self._actor_id,
            )
            await event_bus.emit(f"{self._entity_name}.deleted", {
                "entity_id": entity_id,
                "actor_id": self._actor_id,
            })
        return deleted


class CachedRepository(RepositoryDecorator):
    """In-memory cache for get_by_id reads. Invalidates on write.

    For production use, replace the dict with Redis via shared.config.REDIS_URL.
    """

    def __init__(self, wrapped, ttl_seconds: int = 60):
        super().__init__(wrapped)
        self._cache: dict[int, Any] = {}
        self._entity_name = wrapped.model.__tablename__

    async def get_by_id(self, entity_id: int):
        if entity_id in self._cache:
            logger.debug("cache_hit", entity=self._entity_name, entity_id=entity_id)
            return self._cache[entity_id]

        result = await self._wrapped.get_by_id(entity_id)
        if result:
            self._cache[entity_id] = result
        return result

    async def create(self, data: dict[str, Any]):
        result = await self._wrapped.create(data)
        self._cache[result.id] = result
        return result

    async def update(self, entity_id: int, data: dict[str, Any]):
        result = await self._wrapped.update(entity_id, data)
        if result:
            self._cache[entity_id] = result
        return result

    async def delete(self, entity_id: int) -> bool:
        deleted = await self._wrapped.delete(entity_id)
        self._cache.pop(entity_id, None)
        return deleted

    def invalidate(self, entity_id: int | None = None) -> None:
        """Clear cache for a specific entity or all entities."""
        if entity_id is not None:
            self._cache.pop(entity_id, None)
        else:
            self._cache.clear()

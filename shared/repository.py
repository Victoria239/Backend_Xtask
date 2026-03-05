"""Generic base repository with CRUD operations.

Implements the Repository Pattern with generics to eliminate
duplicated CRUD code across all service repositories.

Usage:
    class ProjectRepository(BaseRepository[Project]):
        model = Project

        async def get_by_status(self, status: str) -> list[Project]:
            ...  # custom queries go here
"""

from typing import Any, Generic, TypeVar

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async repository providing standard CRUD operations.

    Subclasses MUST set the `model` class attribute to the SQLAlchemy model.
    """

    model: type[ModelT]

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Filters ──────────────────────────────────────────────

    def _apply_filters(
        self, query, filters: dict[str, Any] | None = None,
    ):
        """Apply filters to a query. Override in subclasses for custom logic.

        Must return the modified query. Default implementation does exact-match
        on any key that matches a model column.
        """
        if filters:
            for key, value in filters.items():
                column = getattr(self.model, key, None)
                if column is not None and value is not None:
                    query = query.where(column == value)
        return query

    # ─── Read ────────────────────────────────────────────────

    async def get_by_id(self, entity_id: int) -> ModelT | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> list[ModelT]:
        col = getattr(self.model, order_by, None)
        if col is None:
            col = getattr(self.model, "id")
        query = select(self.model).order_by(desc(col) if descending else col)
        query = self._apply_filters(query, filters)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ─── Create ──────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> ModelT:
        entity = self.model(**data)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    # ─── Update ──────────────────────────────────────────────

    async def update(self, entity_id: int, data: dict[str, Any]) -> ModelT | None:
        entity = await self.get_by_id(entity_id)
        if not entity:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    # ─── Paginated Read ────────────────────────────────────────

    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: dict[str, Any] | None = None,
        order_by: str = "created_at",
        descending: bool = True,
    ) -> tuple[list[ModelT], int]:
        """Return (items, total_count) for a paginated query."""
        col = getattr(self.model, order_by, None)
        if col is None:
            col = getattr(self.model, "id")

        base_query = self._apply_filters(select(self.model), filters)
        count_query = self._apply_filters(
            select(func.count()).select_from(self.model), filters,
        )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * page_size
        items_query = (
            base_query
            .order_by(desc(col) if descending else col)
            .offset(offset)
            .limit(page_size)
        )
        result = await self.db.execute(items_query)
        items = list(result.scalars().all())

        return items, total

    # ─── Delete ──────────────────────────────────────────────

    async def delete(self, entity_id: int) -> bool:
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        await self.db.delete(entity)
        await self.db.flush()
        return True

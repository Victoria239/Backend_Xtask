"""Builder Pattern — Fluent builders for complex response objects.

Replaces manual dict/model construction scattered across services
with a step-by-step, readable builder API.

Usage:
    response = (
        ResponseBuilder()
        .with_items(items, ProjectOut)
        .with_pagination(total=100, page=1, page_size=20)
        .with_filters({"estado": "active"})
        .build()
    )
"""

import math
from typing import Any, TypeVar

from pydantic import BaseModel

from shared.schemas import PaginatedResponse, PaginationMeta

T = TypeVar("T", bound=BaseModel)


class ResponseBuilder:
    """Fluent builder for paginated API responses."""

    def __init__(self):
        self._items: list = []
        self._total: int = 0
        self._page: int = 1
        self._page_size: int = 20
        self._extra: dict[str, Any] = {}

    def with_items(self, items: list, schema: type[T] | None = None) -> "ResponseBuilder":
        """Set the response items, optionally validating each through a Pydantic schema."""
        if schema:
            self._items = [schema.model_validate(item) for item in items]
        else:
            self._items = list(items)
        return self

    def with_pagination(self, total: int, page: int, page_size: int) -> "ResponseBuilder":
        """Set pagination parameters."""
        self._total = total
        self._page = page
        self._page_size = page_size
        return self

    def with_filters(self, filters: dict[str, Any] | None) -> "ResponseBuilder":
        """Attach applied filters to the response metadata."""
        if filters:
            self._extra["applied_filters"] = {
                k: v for k, v in filters.items() if v is not None
            }
        return self

    def with_meta(self, key: str, value: Any) -> "ResponseBuilder":
        """Attach arbitrary metadata to the response."""
        self._extra[key] = value
        return self

    def build(self) -> PaginatedResponse:
        """Construct the final PaginatedResponse."""
        return PaginatedResponse(
            data=self._items,
            pagination=PaginationMeta(
                page=self._page,
                pageSize=self._page_size,
                total=self._total,
                totalPages=math.ceil(self._total / self._page_size) if self._page_size > 0 else 0,
            ),
        )

    def build_dict(self) -> dict[str, Any]:
        """Build as a dict (useful for non-paginated or custom responses)."""
        result = self.build().model_dump()
        result.update(self._extra)
        return result

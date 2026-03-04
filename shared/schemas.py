"""Base Pydantic schemas shared across all services."""

import math
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int
    pageSize: int
    total: int
    totalPages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response."""
    data: list[T] = []
    pagination: PaginationMeta

    @classmethod
    def create(cls, items: list, total: int, page: int, page_size: int):
        """Factory to build a paginated response."""
        return cls(
            data=items,
            pagination=PaginationMeta(
                page=page,
                pageSize=page_size,
                total=total,
                totalPages=math.ceil(total / page_size) if page_size > 0 else 0,
            ),
        )

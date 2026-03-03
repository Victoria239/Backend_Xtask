"""Base Pydantic schemas shared across all services."""

import math
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    success: bool = True
    data: T | None = None
    error: str | None = None
    message: str | None = None


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


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


class TimestampMixin(BaseModel):
    """Mixin for created_at / updated_at fields."""
    created_at: datetime | None = None
    updated_at: datetime | None = None

"""Base Pydantic schemas shared across all services."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    success: bool = True
    data: T | None = None
    error: str | None = None
    message: str | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int
    pageSize: int
    total: int
    totalPages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response."""
    success: bool = True
    data: list[T] = []
    pagination: PaginationMeta
    error: str | None = None
    message: str | None = None


class TimestampMixin(BaseModel):
    """Mixin for created_at / updated_at fields."""
    created_at: datetime | None = None
    updated_at: datetime | None = None

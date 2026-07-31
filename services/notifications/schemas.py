"""Notifications service - Pydantic schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NotificationKind = Literal["info", "success", "warning", "error"]


class NotificationCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=1, max_length=255)
    body: str | None = None
    kind: NotificationKind = "info"
    category: str = "general"
    action_url: str | None = None
    meta: dict = Field(default_factory=dict)


class NotificationOut(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    kind: str
    category: str
    title: str
    body: str | None
    action_url: str | None
    meta: dict
    read_at: datetime | None
    archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCount(BaseModel):
    unread: int
    total: int


class MarkReadRequest(BaseModel):
    ids: list[int] | None = None      # si None → marca todas como leídas

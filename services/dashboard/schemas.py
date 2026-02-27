"""Dashboard service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


# ─── Layout schemas ────────────────────────────────────────

class LayoutCreate(BaseModel):
    name: str
    is_default: bool = False


class LayoutUpdate(BaseModel):
    name: str | None = None


class LayoutOut(BaseModel):
    id: int
    user_id: int
    name: str
    is_default: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ─── Widget schemas ────────────────────────────────────────

class WidgetCreate(BaseModel):
    widget_type: str
    title: str
    config: str | None = None
    position_x: int = 0
    position_y: int = 0
    width: int = 1
    height: int = 1


class WidgetUpdate(BaseModel):
    title: str | None = None
    config: str | None = None
    position_x: int | None = None
    position_y: int | None = None
    width: int | None = None
    height: int | None = None


class WidgetOut(BaseModel):
    id: int
    layout_id: int
    widget_type: str
    title: str
    config: str | None = None
    position_x: int
    position_y: int
    width: int
    height: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class WidgetPositionUpdate(BaseModel):
    id: int
    position_x: int
    position_y: int

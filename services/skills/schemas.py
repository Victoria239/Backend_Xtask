"""Skills service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class SkillCreate(BaseModel):
    employee_id: int
    name: str
    category: str | None = None
    level: str = "beginner"
    description: str | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    level: str | None = None
    description: str | None = None


class SkillOut(BaseModel):
    id: int
    employee_id: int
    name: str
    category: str | None = None
    level: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}

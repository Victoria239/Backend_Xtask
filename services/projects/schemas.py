"""Projects service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    status: str = "active"
    start_date: datetime | None = None
    end_date: datetime | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


class ProjectOut(ProjectBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectStatusUpdate(BaseModel):
    estado: str

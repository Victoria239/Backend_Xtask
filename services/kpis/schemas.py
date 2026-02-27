"""KPIs service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class KpiCreate(BaseModel):
    employee_id: int
    name: str
    description: str | None = None
    target_value: float
    period: str


class KpiUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_value: float | None = None
    period: str | None = None


class KpiOut(BaseModel):
    id: int
    employee_id: int
    name: str
    description: str | None = None
    target_value: float
    actual_value: float
    period: str
    status: str
    validated: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class KpiResultUpdate(BaseModel):
    actual_value: float


class KpiValidate(BaseModel):
    validated: bool = True

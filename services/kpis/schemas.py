"""KPIs service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


METRIC_TYPES = {"numeric", "percentage", "currency", "boolean"}
PERIODICITIES = {"weekly", "monthly", "quarterly", "annual"}


class KpiCreate(BaseModel):
    employee_id: int
    name: str
    description: str | None = None
    metric_type: str = "numeric"
    unit: str | None = None
    target_value: float
    weight: float = 1.0
    period: str
    periodicity: str = "monthly"


class KpiUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    metric_type: str | None = None
    unit: str | None = None
    target_value: float | None = None
    weight: float | None = None
    period: str | None = None
    periodicity: str | None = None


class KpiOut(BaseModel):
    id: int
    employee_id: int
    name: str
    description: str | None = None
    metric_type: str = "numeric"
    unit: str | None = None
    target_value: float
    actual_value: float
    weight: float = 1.0
    period: str
    periodicity: str = "monthly"
    status: str
    validated: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class KpiResultUpdate(BaseModel):
    actual_value: float


class KpiValidate(BaseModel):
    validated: bool = True


# ─── C-01: measurement ingestion API ────────────────────────────
class KpiMeasurementIn(BaseModel):
    """Single measurement payload — used both by manual UI and bulk ingestion."""

    kpi_id: int
    value: float
    recorded_at: datetime | None = None
    source: str | None = Field(None, max_length=64)
    notes: str | None = None


class KpiMeasurementBatch(BaseModel):
    measurements: list[KpiMeasurementIn]


class KpiMeasurementOut(BaseModel):
    id: int
    kpi_id: int
    value: float
    recorded_at: datetime
    source: str | None
    notes: str | None

    model_config = {"from_attributes": True}


class KpiMeasurementIngestResponse(BaseModel):
    inserted: int
    updated_kpis: list[int]

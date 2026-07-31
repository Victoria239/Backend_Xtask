"""Predictions service — Pydantic schemas (AI-04)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ForecastPointOut(BaseModel):
    t: datetime
    value: float
    ic_low: float
    ic_high: float


class ForecastResponse(BaseModel):
    kpi_id: int
    kpi_name: str
    horizon: int
    freq_days: float
    method: Literal["linear", "holt", "naive"]
    r2: float | None = None
    last_observed_at: datetime | None
    last_observed_value: float | None
    target: float | None
    forecast: list[ForecastPointOut]
    history: list[ForecastPointOut]


class ForecastRequest(BaseModel):
    horizon: int = Field(default=6, ge=1, le=24)
    freq_days: float = Field(default=30.0, ge=1, le=365)
    method: Literal["linear", "holt", "naive"] | None = None


# ─── AI-06: Attrition risk ──────────────────────────────────────
class AttritionFactorOut(BaseModel):
    code: str
    label: str
    level: float
    weight: float
    contribution: float
    rationale: str


class AttritionResultOut(BaseModel):
    employee_id: int
    employee_name: str
    department: str | None
    position: str | None
    risk_score: int
    risk_band: Literal["low", "medium", "high"]
    factors: list[AttritionFactorOut]
    top_drivers: list[str]


class AttritionListResponse(BaseModel):
    generated_at: datetime
    total_employees: int
    high_risk: int
    medium_risk: int
    low_risk: int
    by_department: dict[str, int]
    employees: list[AttritionResultOut]


# ─── C-06: Comp analytics ───────────────────────────────────────
class CompBandOut(BaseModel):
    department: str
    seniority: str
    headcount: int
    p25: float
    p50: float
    p75: float
    min: float
    max: float


class CompOutlierOut(BaseModel):
    employee_id: int
    name: str
    department: str
    position: str
    seniority: str
    salary: float
    band_p50: float
    compa_ratio: float
    flag: Literal["below", "above"]
    delta_eur: float
    reason: str


class CompOverviewOut(BaseModel):
    total_employees: int
    total_payroll_annual: float
    avg_salary: float
    median_salary: float
    gap_factor: float
    compa_ratio_avg: float
    departments: list[dict]
    bands: list[CompBandOut]
    outliers: list[CompOutlierOut]
    top_earners: list[dict]
    tenure_vs_salary: list[dict]


# ─── H-07: People analytics ─────────────────────────────────────
class NineBoxCellOut(BaseModel):
    perf_tier: int
    retention_tier: int
    label: str
    count: int
    employees: list[dict]


class PeopleOverviewOut(BaseModel):
    total_employees: int
    avg_tenure_months: float
    avg_performance: float
    managers_count: int
    tenure_distribution: list[dict]
    span_of_control: list[dict]
    nine_box: list[NineBoxCellOut]
    segment_risk: list[dict]
    diversity: list[dict]
    band_saturation: dict

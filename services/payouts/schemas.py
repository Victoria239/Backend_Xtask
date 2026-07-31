"""Payouts service — Pydantic schemas (C-04)."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunIn(BaseModel):
    plan_id: int
    period_label: str = Field(min_length=1, max_length=32)
    period_start: date
    period_end: date
    department_filter: str | None = None
    notes: str | None = None
    # Si no se pasa context_overrides, el motor toma datos default por empleado.
    # En MVP: context = {sales: <salary*0.1>, target: <salary*0.15>, ...} para demo.
    context_overrides: dict[int, dict[str, Any]] = Field(default_factory=dict)
    # Llave = employee_id, valor = contexto que sobreescribe los defaults.


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    employee_id: int
    employee_name: str
    department: str | None
    context: dict
    amount: float
    matched_rules: int
    trace: list[dict[str, Any]]
    notes: str | None
    paid_at: date | None
    created_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plan_id: int
    plan_name: str
    period_label: str
    period_start: date
    period_end: date
    department_filter: str | None
    currency: str
    status: str
    total_amount: float
    employee_count: int
    created_at: datetime


class RunDetail(RunSummary):
    payouts: list[PayoutOut] = Field(default_factory=list)


class RunStatusUpdate(BaseModel):
    status: str = Field(pattern="^(draft|pending_approval|approved|paid|cancelled)$")
    note: str | None = None


class PayoutNote(BaseModel):
    notes: str

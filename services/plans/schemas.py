"""Plans service — Pydantic schemas (C-03)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuleIn(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    priority: int = 100
    when: dict[str, Any]  # JSONLogic
    amount: dict[str, Any]  # JSONLogic
    notes: str | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plan_id: int
    label: str
    priority: int
    when: dict[str, Any]
    amount: dict[str, Any]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    scope_department: str | None = None
    scope_role: str | None = None
    period: str = "monthly"
    currency: str = "EUR"
    strategy: str = "first-match"
    defaults: dict[str, Any] = Field(default_factory=dict)
    rules: list[RuleIn] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scope_department: str | None = None
    scope_role: str | None = None
    period: str | None = None
    currency: str | None = None
    strategy: str | None = None
    active: bool | None = None
    defaults: dict[str, Any] | None = None


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    scope_department: str | None
    scope_role: str | None
    period: str
    currency: str
    strategy: str
    active: bool
    rule_count: int = 0
    created_at: datetime


class PlanDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    name: str
    description: str | None
    scope_department: str | None
    scope_role: str | None
    period: str
    currency: str
    strategy: str
    active: bool
    defaults: dict[str, Any]
    rules: list[RuleOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SimulateRequest(BaseModel):
    employee_id: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RuleTrace(BaseModel):
    rule_id: int
    label: str
    matched: bool
    amount: float | None = None
    error: str | None = None


class SimulateResponse(BaseModel):
    plan_id: int
    plan_name: str
    strategy: str
    currency: str
    total_amount: float
    matched_rules: int
    trace: list[RuleTrace]
    context: dict[str, Any]

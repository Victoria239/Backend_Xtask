"""Leaves service — Pydantic schemas (H-04)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ─── Leave Types ────────────────────────────────────────
class LeaveTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    accrual_strategy: str = "annual_grant"
    days_per_year: float = 0
    accrual_config: dict | None = None
    color: str = "#02BDEA"
    requires_approval: bool = True
    allow_negative_balance: bool = False
    active: bool = True


class LeaveTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    accrual_strategy: str
    days_per_year: float
    accrual_config: dict | None
    color: str
    requires_approval: bool
    allow_negative_balance: bool
    active: bool
    created_at: datetime
    updated_at: datetime


# ─── Leaves ────────────────────────────────────────
class LeaveIn(BaseModel):
    type_id: int
    start_date: date
    end_date: date
    reason: str | None = None


class LeaveUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = None


class LeaveDecision(BaseModel):
    """Aprobación o rechazo por parte del manager."""

    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None


class LeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    type_id: int
    type_name: str | None = None
    start_date: date
    end_date: date
    business_days: float
    status: str
    reason: str | None
    approval_note: str | None
    requested_by: int | None
    decided_by: int | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeaveSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    type_id: int
    type_name: str
    type_color: str
    start_date: date
    end_date: date
    business_days: float
    status: str
    created_at: datetime


# ─── Balances ────────────────────────────────────────
class BalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    type_id: int
    type_name: str
    type_color: str
    year: int
    accrued: float
    used: float
    pending: float
    adjustments: float
    available: float  # calculado
    last_computed_at: datetime


class BalanceAdjustment(BaseModel):
    """Ajuste manual del manager: +2 días por buen rendimiento, etc."""

    delta: float
    note: str | None = None


# ─── Events ────────────────────────────────────────
class LeaveEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    leave_id: int
    from_status: str | None
    to_status: str
    note: str | None
    actor_user_id: int | None
    created_at: datetime

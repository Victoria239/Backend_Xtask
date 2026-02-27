"""Payroll service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class PayrollCreate(BaseModel):
    employee_id: int
    period: str
    base_salary: float
    bonuses: float = 0
    deductions: float = 0
    notes: str | None = None


class PayrollUpdate(BaseModel):
    base_salary: float | None = None
    bonuses: float | None = None
    deductions: float | None = None
    notes: str | None = None


class PayrollOut(BaseModel):
    id: int
    employee_id: int
    period: str
    base_salary: float
    bonuses: float
    deductions: float
    net_salary: float
    status: str
    paid_date: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PayrollStatusUpdate(BaseModel):
    status: str

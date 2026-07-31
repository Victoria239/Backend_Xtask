"""Pydantic schemas for Reviews 360°."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class CycleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    period: str = Field(..., min_length=4, max_length=16)
    deadline: date | None = None


class CycleOut(BaseModel):
    id: int
    name: str
    period: str
    status: str
    deadline: date | None
    created_at: datetime
    closed_at: datetime | None
    assignments_count: int = 0
    submitted_count: int = 0

    model_config = {"from_attributes": True}


class AssignmentSummary(BaseModel):
    id: int
    cycle_id: int
    cycle_name: str
    cycle_period: str
    target_employee_id: int
    target_name: str
    role: Literal["self", "manager", "peer", "report"]
    status: str


class QuestionOut(BaseModel):
    code: str
    category: str
    text: str


class FormResponse(BaseModel):
    question_code: str
    score: int = Field(..., ge=1, le=5)
    comment: str | None = None


class SubmitRequest(BaseModel):
    responses: list[FormResponse] = Field(..., min_length=1)


class SummaryOut(BaseModel):
    cycle_id: int
    cycle_name: str
    cycle_period: str
    employee_id: int
    employee_name: str
    overall_score: float
    by_category: dict[str, float]
    by_role: dict[str, float]
    responses_count: int

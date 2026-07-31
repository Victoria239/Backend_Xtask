"""Onboarding service - Pydantic schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

StepStatus = Literal["pending", "in_progress", "done", "skipped"]


# ─── Templates ───────────────────────────────────────────────────
class TemplateStepIn(BaseModel):
    position: int = 0
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    category: str = "general"
    due_days: int = 7
    required: bool = True


class TemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    is_default: bool = False
    steps: list[TemplateStepIn] = Field(default_factory=list)


class TemplateStepOut(TemplateStepIn):
    id: int

    model_config = {"from_attributes": True}


class TemplateOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    description: str | None
    is_default: bool
    created_at: datetime
    steps: list[TemplateStepOut] = []

    model_config = {"from_attributes": True}


# ─── Assignments ─────────────────────────────────────────────────
class AssignRequest(BaseModel):
    employee_id: int
    template_id: int | None = None       # si None usa el default del tenant


class AssignmentStepOut(BaseModel):
    id: int
    assignment_id: int
    position: int
    title: str
    description: str | None
    category: str
    required: bool
    due_date: date | None
    status: str
    completed_at: datetime | None
    completed_by: int | None

    model_config = {"from_attributes": True}


class AssignmentOut(BaseModel):
    id: int
    tenant_id: int
    employee_id: int
    template_id: int | None
    started_at: datetime
    completed_at: datetime | None
    steps: list[AssignmentStepOut] = []

    model_config = {"from_attributes": True}


class StepUpdate(BaseModel):
    status: StepStatus


class AssignmentSummary(BaseModel):
    """Para el dashboard admin: progreso global de todas las asignaciones."""
    assignment_id: int
    employee_id: int
    employee_name: str
    total_steps: int
    done_steps: int
    completed_at: datetime | None
    started_at: datetime

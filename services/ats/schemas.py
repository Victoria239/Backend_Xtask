"""ATS service — Pydantic schemas (H-03)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─── Stages ────────────────────────────────────────
class StageIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    position: int = 0
    is_terminal: bool = False
    color: str = "#605C70"


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pipeline_id: int
    name: str
    position: int
    is_terminal: bool
    color: str


# ─── Pipelines ────────────────────────────────────────
class PipelineIn(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    department: str | None = None
    location: str | None = None
    hiring_manager_employee_id: int | None = None
    status: str = "open"
    # Si vacío al crear, se siembran 5 stages estándar
    stages: list[StageIn] = Field(default_factory=list)


class PipelineUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    department: str | None = None
    location: str | None = None
    hiring_manager_employee_id: int | None = None
    status: str | None = None


class PipelineSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    department: str | None
    location: str | None
    status: str
    hiring_manager_employee_id: int | None
    created_at: datetime
    application_count: int = 0


class PipelineDetail(PipelineSummary):
    stages: list[StageOut] = Field(default_factory=list)


# ─── Candidates ────────────────────────────────────────
class CandidateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    resume_url: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    source: str | None = None


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    resume_url: str | None
    tags: list[str] | None
    notes: str | None
    source: str | None
    created_at: datetime
    updated_at: datetime


# ─── Applications ────────────────────────────────────────
class ApplicationIn(BaseModel):
    candidate_id: int
    expected_salary: str | None = None


class MoveStage(BaseModel):
    to_stage_id: int
    note: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pipeline_id: int
    candidate_id: int
    stage_id: int
    final_decision: str | None
    expected_salary: str | None
    offered_salary: str | None
    created_at: datetime
    updated_at: datetime


class KanbanCard(BaseModel):
    """Card de candidato dentro del kanban view."""

    application_id: int
    candidate_id: int
    candidate_name: str
    candidate_email: str | None
    candidate_source: str | None
    stage_id: int
    days_in_stage: int


class KanbanColumn(BaseModel):
    stage: StageOut
    cards: list[KanbanCard] = Field(default_factory=list)


class KanbanView(BaseModel):
    pipeline_id: int
    pipeline_title: str
    columns: list[KanbanColumn] = Field(default_factory=list)


# ─── Events ────────────────────────────────────────
class ApplicationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    kind: str
    from_stage_id: int | None
    to_stage_id: int | None
    note: str | None
    actor_user_id: int | None
    created_at: datetime


DEFAULT_STAGES: list[dict[str, Any]] = [
    {"name": "Sourced", "position": 10, "color": "#605C70"},
    {"name": "Phone screen", "position": 20, "color": "#02BDEA"},
    {"name": "Interview", "position": 30, "color": "#01E3D5"},
    {"name": "Offer", "position": 40, "color": "#E08A0E"},
    {"name": "Hired", "position": 50, "color": "#01B89E", "is_terminal": True},
    {"name": "Rejected", "position": 60, "color": "#D14040", "is_terminal": True},
]

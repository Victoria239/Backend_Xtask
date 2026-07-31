"""Approvals service — Pydantic schemas (C-05)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    position: int
    approver_role: str
    approver_user_id: int | None = None
    auto_approve_below: float | None = None
    sla_hours: int = 72


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    flow_id: int
    position: int
    name: str
    approver_role: str
    approver_user_id: int | None
    auto_approve_below: float | None
    sla_hours: int


class FlowIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    target_kind: str = Field(min_length=1, max_length=32)
    priority: int = 100
    active: bool = True
    filter_jsonlogic: dict | None = None
    steps: list[StepIn] = Field(default_factory=list)


class FlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    target_kind: str
    priority: int
    active: bool
    filter_jsonlogic: dict | None
    created_at: datetime


class FlowDetail(FlowOut):
    steps: list[StepOut] = Field(default_factory=list)


class InstanceStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    instance_id: int
    position: int
    name: str
    approver_user_id: int | None
    status: str
    decided_at: datetime | None
    decided_by: int | None
    note: str | None


class InstanceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    flow_id: int
    target_kind: str
    target_id: int
    status: str
    current_step_position: int
    summary: str | None
    target_employee_id: int | None
    requester_user_id: int | None
    created_at: datetime


class InstanceDetail(InstanceSummary):
    steps: list[InstanceStepOut] = Field(default_factory=list)


class StartInstance(BaseModel):
    target_kind: str
    target_id: int
    summary: str
    target_employee_id: int | None = None
    requester_user_id: int | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class StepDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None

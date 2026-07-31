"""OKRs service — Pydantic schemas (C-02)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ─── Key Result ─────────────────────────────────────────
class KeyResultIn(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    metric_type: str = Field(default="numeric")
    unit: str | None = None
    baseline: float = 0
    target: float
    current: float = 0
    weight: float = 1.0
    linked_kpi_id: int | None = None


class KeyResultUpdate(BaseModel):
    name: str | None = None
    metric_type: str | None = None
    unit: str | None = None
    baseline: float | None = None
    target: float | None = None
    current: float | None = None
    weight: float | None = None
    linked_kpi_id: int | None = None


class KeyResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    okr_id: int
    name: str
    metric_type: str
    unit: str | None
    baseline: float
    target: float
    current: float
    weight: float
    linked_kpi_id: int | None
    progress: float = 0  # calculated
    created_at: datetime
    updated_at: datetime


# ─── OKR ─────────────────────────────────────────
class OkrIn(BaseModel):
    scope: str = Field(default="company")  # company|team|individual
    parent_id: int | None = None
    owner_employee_id: int | None = None
    owner_department: str | None = None
    objective: str = Field(min_length=1, max_length=256)
    description: str | None = None
    period: str = Field(min_length=1, max_length=32)
    weight: float = 1.0
    key_results: list[KeyResultIn] = Field(default_factory=list)


class OkrUpdate(BaseModel):
    scope: str | None = None
    parent_id: int | None = None
    owner_employee_id: int | None = None
    owner_department: str | None = None
    objective: str | None = None
    description: str | None = None
    period: str | None = None
    weight: float | None = None


class OkrOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: int | None
    scope: str
    owner_employee_id: int | None
    owner_department: str | None
    objective: str
    description: str | None
    period: str
    status: str
    progress: float
    weight: float
    created_at: datetime
    updated_at: datetime


class OkrDetail(OkrOut):
    key_results: list[KeyResultOut] = Field(default_factory=list)


class OkrTreeNode(OkrOut):
    key_results: list[KeyResultOut] = Field(default_factory=list)
    children: list["OkrTreeNode"] = Field(default_factory=list)


OkrTreeNode.model_rebuild()


# ─── Check-ins ─────────────────────────────────────────
class CheckinIn(BaseModel):
    kr_id: int
    value: float
    confidence: str | None = None
    comment: str | None = None


class CheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kr_id: int
    value: float
    confidence: str | None
    comment: str | None
    source: str
    created_by: int | None
    created_at: datetime


# ─── What-if (AI-07) ─────────────────────────────────────────
class WhatIfRequest(BaseModel):
    """Sobrescribe el current de N KRs y devuelve la cascada simulada SIN persistir."""

    kr_overrides: dict[int, float] = Field(default_factory=dict)
    # Llave = kr_id, valor = nuevo current


class WhatIfOkr(BaseModel):
    id: int
    parent_id: int | None
    objective: str
    scope: str
    period: str
    # Estado actual (de la DB)
    current_progress: float
    current_status: str
    # Estado simulado
    sim_progress: float
    sim_status: str
    # Diff
    delta_progress: float


class WhatIfKr(BaseModel):
    id: int
    okr_id: int
    name: str
    baseline: float
    target: float
    current: float
    sim_current: float
    current_progress: float
    sim_progress: float


class WhatIfResponse(BaseModel):
    period: str | None
    affected_okrs: list[WhatIfOkr]
    affected_krs: list[WhatIfKr]

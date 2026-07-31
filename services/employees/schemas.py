"""Employees service - Pydantic schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    position: str
    department: str
    salary: float
    contract_status: str = "active"
    manager_id: int | None = None
    hire_date: date | None = None
    custom_fields: dict = Field(default_factory=dict)


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    department: str | None = None
    salary: float | None = None
    contract_status: str | None = None
    manager_id: int | None = None
    hire_date: date | None = None
    custom_fields: dict | None = None


class EmployeeOut(BaseModel):
    id: int
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    position: str
    department: str
    salary: float
    contract_status: str
    manager_id: int | None = None
    hire_date: date | None = None
    custom_fields: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmployeeProjectAssign(BaseModel):
    project_ids: list[int]


# ─── H-01: org chart ────────────────────────────────────────────
class OrgNode(BaseModel):
    id: int
    full_name: str
    position: str
    department: str
    manager_id: int | None = None
    reports: list["OrgNode"] = Field(default_factory=list)


OrgNode.model_rebuild()


# ─── H-01: employee documents ──────────────────────────────────
class EmployeeDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    doc_type: str = "other"  # contract|cert|id|policy|other
    storage_uri: str | None = None
    content: str | None = None
    meta: dict = Field(default_factory=dict)


class EmployeeDocumentOut(BaseModel):
    id: int
    employee_id: int
    title: str
    doc_type: str
    storage_uri: str | None = None
    content: str | None = None
    meta: dict
    created_at: datetime

    model_config = {"from_attributes": True}

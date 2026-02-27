"""Employees service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class EmployeeCreate(BaseModel):
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    position: str
    department: str
    salary: str
    contract_status: str = "active"


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    position: str | None = None
    department: str | None = None
    salary: str | None = None
    contract_status: str | None = None


class EmployeeOut(BaseModel):
    id: int
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    position: str
    department: str
    salary: str
    contract_status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmployeeProjectAssign(BaseModel):
    project_ids: list[int]

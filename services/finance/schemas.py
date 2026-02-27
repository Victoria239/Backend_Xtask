"""Finance service - Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


# ─── Budget schemas ────────────────────────────────────────

class BudgetCreate(BaseModel):
    project_id: int | None = None
    name: str
    description: str | None = None
    total_amount: float
    status: str = "active"


class BudgetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    total_amount: float | None = None
    spent_amount: float | None = None
    status: str | None = None


class BudgetOut(BaseModel):
    id: int
    project_id: int | None = None
    name: str
    description: str | None = None
    total_amount: float
    spent_amount: float
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExpenseRegister(BaseModel):
    amount: float
    description: str | None = None


# ─── Invoice schemas ───────────────────────────────────────

class InvoiceCreate(BaseModel):
    project_id: int | None = None
    invoice_number: str
    client: str
    description: str | None = None
    amount: float
    status: str = "pending"
    due_date: datetime | None = None


class InvoiceUpdate(BaseModel):
    client: str | None = None
    description: str | None = None
    amount: float | None = None
    status: str | None = None
    due_date: datetime | None = None


class InvoiceOut(BaseModel):
    id: int
    project_id: int | None = None
    invoice_number: str
    client: str
    description: str | None = None
    amount: float
    status: str
    due_date: datetime | None = None
    paid_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InvoiceStatusUpdate(BaseModel):
    status: str

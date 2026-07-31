"""Employees service - SQLAlchemy models."""

from datetime import datetime, date

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = {"schema": "svc_employees"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String, nullable=True)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[str] = mapped_column(String, nullable=False)
    department: Mapped[str] = mapped_column(String, nullable=False)
    salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    contract_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # H-01 enhancements
    manager_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    custom_fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EmployeeProject(Base):
    __tablename__ = "employee_projects"
    __table_args__ = {"schema": "svc_employees"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False)


class EmployeeDocument(Base):
    """H-01: Documents attached to an employee profile (contracts, certs, IDs)."""

    __tablename__ = "employee_documents"
    __table_args__ = {"schema": "svc_employees"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    storage_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

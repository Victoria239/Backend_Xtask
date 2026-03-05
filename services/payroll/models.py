"""Payroll service - SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Payroll(Base):
    __tablename__ = "payrolls"
    __table_args__ = {"schema": "svc_payroll"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    base_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    bonuses: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    deductions: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_salary: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    paid_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

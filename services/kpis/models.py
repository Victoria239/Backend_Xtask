"""KPIs service - SQLAlchemy models."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Kpi(Base):
    __tablename__ = "kpis"
    __table_args__ = {"schema": "svc_kpis"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    employee_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # C-01: KPI taxonomy
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False, default="numeric")  # numeric|percentage|currency|boolean
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    actual_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=1.0)
    period: Mapped[str] = mapped_column(String, nullable=False)
    periodicity: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")  # monthly|quarterly|annual
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    validated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class KpiMeasurement(Base):
    """C-01: Time-series of KPI actual values for ingestion API."""

    __tablename__ = "kpi_measurements"
    __table_args__ = {"schema": "svc_kpis"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kpi_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

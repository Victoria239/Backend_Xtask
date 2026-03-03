"""Payroll microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.payroll.router import router

app = create_service_app(
    title="XTask Payroll Service",
    service_name="payroll-service",
    prefix="/api/nominas",
)

app.include_router(router, prefix="/api/nominas", tags=["Payroll"])

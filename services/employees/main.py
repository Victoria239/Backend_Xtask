"""Employees microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.employees.router import router

app = create_service_app(
    title="XTask Employees Service",
    service_name="employees-service",
    prefix="/api/empleados",
)

app.include_router(router, prefix="/api/empleados", tags=["Employees"])

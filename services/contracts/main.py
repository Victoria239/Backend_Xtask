"""Contracts microservice — standalone entry point (E-02)."""

from shared.service_app import create_service_app
from services.contracts.router import router

app = create_service_app(
    title="XTask Contracts Service",
    service_name="contracts-service",
    prefix="/api/contracts",
)

app.include_router(router, prefix="/api/contracts", tags=["Contracts"])

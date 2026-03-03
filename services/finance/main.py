"""Finance microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.finance.router import router

app = create_service_app(
    title="XTask Finance Service",
    service_name="finance-service",
    prefix="/api/finanzas",
)

app.include_router(router, prefix="/api/finanzas", tags=["Finance"])

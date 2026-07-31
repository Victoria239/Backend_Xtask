"""Payouts microservice — standalone entry point (C-04)."""

from shared.service_app import create_service_app
from services.payouts.router import router

app = create_service_app(
    title="XTask Payouts Service",
    service_name="payouts-service",
    prefix="/api/payouts",
)

app.include_router(router, prefix="/api/payouts", tags=["Payouts"])

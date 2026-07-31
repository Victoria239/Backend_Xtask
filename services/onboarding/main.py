"""Onboarding microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.onboarding.router import router

app = create_service_app(
    title="XTask Onboarding Service",
    service_name="onboarding-service",
    prefix="/api/onboarding",
)

app.include_router(router, prefix="/api/onboarding", tags=["Onboarding"])

"""Predictions microservice — standalone entry point (AI-04)."""

from shared.service_app import create_service_app
from services.predictions.router import router

app = create_service_app(
    title="XTask Predictions Service",
    service_name="predictions-service",
    prefix="/api/predictions",
)

app.include_router(router, prefix="/api/predictions", tags=["Predictions"])

"""Leaves microservice — standalone entry point (H-04)."""

from shared.service_app import create_service_app
from services.leaves.router import router

app = create_service_app(
    title="XTask Leaves Service",
    service_name="leaves-service",
    prefix="/api/leaves",
)

app.include_router(router, prefix="/api/leaves", tags=["Leaves"])

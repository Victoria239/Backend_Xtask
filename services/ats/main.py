"""ATS microservice — standalone entry point (H-03)."""

from shared.service_app import create_service_app
from services.ats.router import router

app = create_service_app(
    title="XTask ATS Service",
    service_name="ats-service",
    prefix="/api/ats",
)

app.include_router(router, prefix="/api/ats", tags=["ATS"])

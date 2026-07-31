"""Plans microservice — standalone entry point (C-03)."""

from shared.service_app import create_service_app
from services.plans.router import router

app = create_service_app(
    title="XTask Plans Service",
    service_name="plans-service",
    prefix="/api/plans",
)

app.include_router(router, prefix="/api/plans", tags=["Plans"])

"""Dashboard microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.dashboard.router import router

app = create_service_app(
    title="XTask Dashboard Service",
    service_name="dashboard-service",
    prefix="/api/dashboard",
)

app.include_router(router, prefix="/api/dashboard", tags=["Dashboard"])

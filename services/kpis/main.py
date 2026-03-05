"""KPIs microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.kpis.router import router

app = create_service_app(
    title="XTask KPIs Service",
    service_name="kpis-service",
    prefix="/api/kpis",
)

app.include_router(router, prefix="/api/kpis", tags=["KPIs"])

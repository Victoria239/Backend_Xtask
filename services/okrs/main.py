"""OKRs microservice — standalone entry point (C-02)."""

from shared.service_app import create_service_app
from services.okrs.router import router

app = create_service_app(
    title="XTask OKRs Service",
    service_name="okrs-service",
    prefix="/api/okrs",
)

app.include_router(router, prefix="/api/okrs", tags=["OKRs"])

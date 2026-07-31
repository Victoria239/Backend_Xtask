"""Approvals microservice — standalone entry point (C-05)."""

from shared.service_app import create_service_app
from services.approvals.router import router

app = create_service_app(
    title="XTask Approvals Service",
    service_name="approvals-service",
    prefix="/api/approvals",
)

app.include_router(router, prefix="/api/approvals", tags=["Approvals"])

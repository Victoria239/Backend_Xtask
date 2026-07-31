"""Notifications microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.notifications.router import router

app = create_service_app(
    title="XTask Notifications Service",
    service_name="notifications-service",
    prefix="/api/notifications",
)

app.include_router(router, prefix="/api/notifications", tags=["Notifications"])

"""Auth microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.auth.router import router

app = create_service_app(
    title="XTask Auth Service",
    service_name="auth-service",
    prefix="/api/auth",
)

app.include_router(router, prefix="/api/auth", tags=["Auth"])

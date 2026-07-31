"""Tasks microservice — standalone entry point (Tablero de Actividades)."""

from shared.service_app import create_service_app
from services.tasks.router import router

app = create_service_app(
    title="XTask Tasks Service",
    service_name="tasks-service",
    prefix="/api/actividades",
)

app.include_router(router, prefix="/api/actividades", tags=["Actividades"])

"""Projects microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.projects.router import router

app = create_service_app(
    title="XTask Projects Service",
    service_name="projects-service",
    prefix="/api/proyectos",
)

app.include_router(router, prefix="/api/proyectos", tags=["Projects"])

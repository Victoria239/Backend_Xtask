"""Skills microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.skills.router import router

app = create_service_app(
    title="XTask Skills Service",
    service_name="skills-service",
    prefix="/api/habilidades",
)

app.include_router(router, prefix="/api/habilidades", tags=["Skills"])

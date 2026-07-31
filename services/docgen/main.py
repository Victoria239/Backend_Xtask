"""DocGen microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.docgen.router import router

app = create_service_app(
    title="XTask DocGen Service",
    service_name="docgen-service",
    prefix="/api/docgen",
)

app.include_router(router, prefix="/api/docgen", tags=["DocGen"])

"""Reviews 360° microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.reviews.router import router

app = create_service_app(
    title="XTask Reviews 360°",
    service_name="reviews-service",
    prefix="/api/reviews",
)

app.include_router(router, prefix="/api/reviews", tags=["Reviews"])

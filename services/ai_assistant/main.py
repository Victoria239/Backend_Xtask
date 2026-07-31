"""AI Assistant microservice — standalone entry point."""

from shared.service_app import create_service_app
from services.ai_assistant.router import router

app = create_service_app(
    title="XTask AI Assistant",
    service_name="ai-assistant",
    prefix="/api/ai",
)

app.include_router(router, prefix="/api/ai", tags=["AI Assistant"])

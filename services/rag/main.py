"""RAG microservice — standalone entry point.

Q5 Fase 4.C3: este servicio ahora aloja **solo** los endpoints de RAG.
Los co-hosts de tenants, dashboard y reviews se movieron a sus propios
containers (ver compose).
"""
from shared.service_app import create_service_app
from services.rag.router import router

app = create_service_app(
    title="XTask RAG Service",
    service_name="rag-service",
    prefix="/api/rag",
)

app.include_router(router, prefix="/api/rag", tags=["RAG"])

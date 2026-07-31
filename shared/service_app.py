"""Factory for creating standalone FastAPI microservice apps.

Each service uses this to bootstrap itself with shared middleware,
exception handlers, logging, and database initialization.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import APP_VERSION, get_settings
from shared.database import init_db
from shared.logging import setup_logging, get_logger
from shared.metrics import setup_metrics
from shared.middleware import (
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)
from shared.swagger_theme import install_xtask_swagger

logger = get_logger(__name__)


def create_service_app(
    title: str,
    service_name: str,
    version: str = APP_VERSION,
    prefix: str = "",
) -> FastAPI:
    """Create a FastAPI app for a standalone microservice."""

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging()
        logger.info(f"starting_{service_name}", environment=settings.ENVIRONMENT)
        if settings.is_development:
            await init_db()
            logger.info("database_initialized")
        yield
        logger.info(f"shutting_down_{service_name}")

    docs_url = f"{prefix}/docs" if settings.is_development else None
    openapi_url = f"{prefix}/openapi.json" if settings.is_development else None

    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan,
        docs_url=None,  # reemplazado por install_xtask_swagger
        redoc_url=f"{prefix}/redoc" if settings.is_development else None,
        openapi_url=openapi_url,
    )

    # ─── Middleware ─────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Request-ID"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # ─── Exception handlers ────────────────────────────────
    register_exception_handlers(app)

    # ─── Health check ──────────────────────────────────────
    @app.get(f"{prefix}/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "service": service_name, "version": version}

    # ─── Prometheus metrics (Sprint 7) ─────────────────────
    # Expone /metrics en raíz para que Prometheus scrape el mismo path en todos los services.
    setup_metrics(app, service_name=service_name, metrics_path="/metrics")

    # ─── Swagger UI custom (alineado con DESIGN.md) ────────
    if settings.is_development and docs_url and openapi_url:
        app.docs_url = docs_url
        install_xtask_swagger(app, openapi_url=openapi_url, title=title)

    return app

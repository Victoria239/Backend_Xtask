"""
XTask API Gateway
Main entry point that routes requests to the appropriate microservices.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.database import init_db
from shared.logging import setup_logging, get_logger

# Import service routers
from services.auth.router import router as auth_router
from services.projects.router import router as projects_router
from services.employees.router import router as employees_router
from services.finance.router import router as finance_router
from services.payroll.router import router as payroll_router
from services.kpis.router import router as kpis_router
from services.skills.router import router as skills_router
from services.dashboard.router import router as dashboard_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    setup_logging()
    settings = get_settings()
    logger.info("starting_gateway", environment=settings.ENVIRONMENT, port=settings.GATEWAY_PORT)

    if settings.is_development:
        await init_db()
        logger.info("database_initialized")

    yield

    logger.info("shutting_down_gateway")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="XTask API",
        description="Backend API for XTask - Project & Finance Management",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url="/api/openapi.json" if settings.is_development else None,
    )

    # ─── CORS ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    # ─── Register service routers ────────────────────────────
    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(projects_router, prefix="/api/proyectos", tags=["Projects"])
    app.include_router(employees_router, prefix="/api/empleados", tags=["Employees"])
    app.include_router(finance_router, prefix="/api/finanzas", tags=["Finance"])
    app.include_router(payroll_router, tags=["Payroll"])
    app.include_router(kpis_router, prefix="/api/kpis", tags=["KPIs"])
    app.include_router(skills_router, prefix="/api/habilidades", tags=["Skills"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])

    # ─── Health check ────────────────────────────────────────
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "service": "xtask-gateway", "version": "0.1.0"}

    return app


app = create_app()

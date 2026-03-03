"""
XTask API Gateway
Reverse proxy that routes requests to the appropriate microservices.

In development mode (GATEWAY_MODE=monolith), it imports routers directly.
In production mode (GATEWAY_MODE=proxy), it forwards requests via HTTP.
"""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.database import init_db
from shared.logging import setup_logging, get_logger
from shared.middleware import (
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)

logger = get_logger(__name__)

# ─── Service route mapping ─────────────────────────────────────
SERVICE_ROUTES: dict[str, str] = {}
_http_client: httpx.AsyncClient | None = None


def _build_service_routes():
    """Build route prefix -> service URL mapping from settings."""
    settings = get_settings()
    return {
        "/api/auth": settings.AUTH_SERVICE_URL,
        "/api/proyectos": settings.PROJECTS_SERVICE_URL,
        "/api/empleados": settings.EMPLOYEES_SERVICE_URL,
        "/api/finanzas": settings.FINANCE_SERVICE_URL,
        "/api/nominas": settings.PAYROLL_SERVICE_URL,
        "/api/kpis": settings.KPIS_SERVICE_URL,
        "/api/habilidades": settings.SKILLS_SERVICE_URL,
        "/api/dashboard": settings.DASHBOARD_SERVICE_URL,
    }


# ─── Reverse proxy handler ────────────────────────────────────
async def _proxy_request(request: Request, target_url: str) -> Response:
    """Forward an incoming request to the target microservice."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)

    url = f"{target_url}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    try:
        resp = await _http_client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
    except httpx.ConnectError:
        return Response(
            content='{"success":false,"error":"Service unavailable"}',
            status_code=503,
            media_type="application/json",
        )

    excluded_headers = {"content-encoding", "content-length", "transfer-encoding"}
    response_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    global _http_client, SERVICE_ROUTES
    setup_logging()
    settings = get_settings()
    logger.info(
        "starting_gateway",
        environment=settings.ENVIRONMENT,
        port=settings.GATEWAY_PORT,
        mode=settings.GATEWAY_MODE,
    )

    if settings.GATEWAY_MODE == "monolith":
        await init_db()
        logger.info("database_initialized")
    else:
        SERVICE_ROUTES.update(_build_service_routes())
        _http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("proxy_mode_enabled", services=list(SERVICE_ROUTES.keys()))

    yield

    if _http_client:
        await _http_client.aclose()
    logger.info("shutting_down_gateway")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="XTask API Gateway",
        description="Reverse proxy gateway for XTask microservices",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url="/api/openapi.json" if settings.is_development else None,
    )

    # ─── Middleware (order matters: last added = first executed) ─
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

    # ─── Exception handlers ──────────────────────────────────
    register_exception_handlers(app)

    # ─── Health check ────────────────────────────────────────
    @app.get("/api/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "service": "xtask-gateway", "version": "0.2.0", "mode": settings.GATEWAY_MODE}

    @app.get("/api/health/services", tags=["Health"])
    async def services_health():
        """Check health of all downstream services (proxy mode only)."""
        if settings.GATEWAY_MODE == "monolith":
            return {"mode": "monolith", "message": "All services run in-process"}

        results = {}
        for prefix, url in SERVICE_ROUTES.items():
            svc_name = prefix.replace("/api/", "")
            try:
                resp = await _http_client.get(f"{url}{prefix}/health", timeout=5.0)
                results[svc_name] = {"status": "ok", "url": url} if resp.status_code == 200 else {"status": "unhealthy", "url": url}
            except Exception:
                results[svc_name] = {"status": "unreachable", "url": url}
        return {"mode": "proxy", "services": results}

    # ─── Mode-dependent routing ──────────────────────────────
    if settings.GATEWAY_MODE == "monolith":
        _register_monolith_routers(app)
    else:
        routes = _build_service_routes()
        _register_proxy_routes(app, routes)

    return app


def _register_monolith_routers(app: FastAPI):
    """Import and register routers directly (monolith mode)."""
    from services.auth.router import router as auth_router
    from services.projects.router import router as projects_router
    from services.employees.router import router as employees_router
    from services.finance.router import router as finance_router
    from services.payroll.router import router as payroll_router
    from services.kpis.router import router as kpis_router
    from services.skills.router import router as skills_router
    from services.dashboard.router import router as dashboard_router

    app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    app.include_router(projects_router, prefix="/api/proyectos", tags=["Projects"])
    app.include_router(employees_router, prefix="/api/empleados", tags=["Employees"])
    app.include_router(finance_router, prefix="/api/finanzas", tags=["Finance"])
    app.include_router(payroll_router, prefix="/api/nominas", tags=["Payroll"])
    app.include_router(kpis_router, prefix="/api/kpis", tags=["KPIs"])
    app.include_router(skills_router, prefix="/api/habilidades", tags=["Skills"])
    app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])


def _register_proxy_routes(app: FastAPI, routes: dict[str, str]):
    """Register catch-all routes that proxy to downstream services."""
    for prefix, target in routes.items():
        _add_proxy_route(app, prefix, target)


def _add_proxy_route(app: FastAPI, prefix: str, target: str):
    """Add catch-all routes for a specific service prefix."""
    tag = prefix.replace("/api/", "").capitalize()

    async def _forward(request: Request, _target: str = target) -> Response:
        return await _proxy_request(request, _target)

    app.add_api_route(
        prefix,
        _forward,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        tags=[tag],
        name=f"proxy_{tag.lower()}_root",
    )

    async def _forward_sub(request: Request, path: str, _target: str = target) -> Response:
        return await _proxy_request(request, _target)

    app.add_api_route(
        f"{prefix}/{{path:path}}",
        _forward_sub,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        tags=[tag],
        name=f"proxy_{tag.lower()}_sub",
    )


app = create_app()

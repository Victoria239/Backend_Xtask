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

from shared.config import APP_VERSION, get_settings
from shared.database import init_db
from shared.logging import setup_logging, get_logger
from shared.middleware import (
    RequestIdMiddleware,
    RequestLoggingMiddleware,
    register_exception_handlers,
)

logger = get_logger(__name__)


# ─── Proxy client ──────────────────────────────────────────────
class ProxyClient:
    """Encapsulates HTTP client and service route mapping for proxy mode."""

    def __init__(self):
        self.routes: dict[str, str] = {}
        self._client: httpx.AsyncClient | None = None

    def build_routes(self):
        settings = get_settings()
        self.routes = {
            "/api/auth":      settings.AUTH_SERVICE_URL,
            "/api/proyectos": settings.PROJECTS_SERVICE_URL,
            "/api/empleados": settings.EMPLOYEES_SERVICE_URL,
            "/api/nominas":   settings.PAYROLL_SERVICE_URL,
            "/api/finanzas":  settings.FINANCE_SERVICE_URL,
            "/api/kpis":      settings.KPIS_SERVICE_URL,
            "/api/habilidades": settings.SKILLS_SERVICE_URL,
            "/api/rag":       settings.RAG_SERVICE_URL,
            "/api/ai":        settings.AI_ASSISTANT_SERVICE_URL,
            # Q5 Fase 4.C3 — services split out de rag a containers independientes
            "/api/tenants":   settings.TENANTS_SERVICE_URL,
            "/api/dashboard": settings.DASHBOARD_SERVICE_URL,
            "/api/reviews":   settings.REVIEWS_SERVICE_URL,
            "/api/notifications": settings.NOTIFICATIONS_SERVICE_URL,
            "/api/onboarding":    settings.ONBOARDING_SERVICE_URL,
            "/api/docgen":        settings.DOCGEN_SERVICE_URL,
            "/api/okrs":          settings.OKRS_SERVICE_URL,
            "/api/contracts":     settings.CONTRACTS_SERVICE_URL,
            "/api/plans":         settings.PLANS_SERVICE_URL,
            "/api/leaves":        settings.LEAVES_SERVICE_URL,
            "/api/ats":           settings.ATS_SERVICE_URL,
            "/api/payouts":       settings.PAYOUTS_SERVICE_URL,
            "/api/approvals":     settings.APPROVALS_SERVICE_URL,
            "/api/predictions":   settings.PREDICTIONS_SERVICE_URL,
            "/api/actividades":   settings.TASKS_SERVICE_URL,
        }

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def forward(self, request: Request, target_url: str) -> Response:
        """Forward an incoming request to the target microservice."""
        # Bloquear endpoints internos para evitar cross-tenant leak vía gateway público.
        # Las rutas /api/*/internal/* deben ser invocables solo desde la red Docker interna,
        # no desde el navegador del usuario.
        if "/internal/" in request.url.path:
            return Response(
                content='{"success":false,"error":"Not found"}',
                status_code=404,
                media_type="application/json",
            )
        url = f"{target_url}{request.url.path}"
        if request.url.query:
            url = f"{url}?{request.url.query}"

        headers = dict(request.headers)
        headers.pop("host", None)
        body = await request.body()

        try:
            resp = await self.client.request(
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

        excluded = {"content-encoding", "content-length", "transfer-encoding"}
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=resp.headers.get("content-type"),
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


proxy = ProxyClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
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
        proxy.build_routes()
        logger.info("proxy_mode_enabled", services=list(proxy.routes.keys()))

    yield

    await proxy.close()
    logger.info("shutting_down_gateway")


def create_app() -> FastAPI:
    settings = get_settings()

    docs_url = "/api/docs" if settings.is_development else None
    openapi_url = "/api/openapi.json" if settings.is_development else None

    app = FastAPI(
        title="XTask API Gateway",
        description="Reverse proxy gateway for XTask microservices",
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url=None,  # reemplazado por install_xtask_swagger
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url=openapi_url,
    )

    if settings.is_development and docs_url and openapi_url:
        from shared.swagger_theme import install_xtask_swagger
        app.docs_url = docs_url
        install_xtask_swagger(app, openapi_url=openapi_url, title="XTask API Gateway")

    # ─── Prometheus metrics (Sprint 7) ─────────────────────
    from shared.metrics import setup_metrics
    setup_metrics(app, service_name="gateway", metrics_path="/metrics")

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
        return {"status": "ok", "service": "xtask-gateway", "version": APP_VERSION, "mode": settings.GATEWAY_MODE}

    @app.get("/api/health/services", tags=["Health"])
    async def services_health():
        """Check health of all downstream services (proxy mode only)."""
        if settings.GATEWAY_MODE == "monolith":
            return {"mode": "monolith", "message": "All services run in-process"}

        results = {}
        for prefix, url in proxy.routes.items():
            svc_name = prefix.replace("/api/", "")
            try:
                resp = await proxy.client.get(f"{url}{prefix}/health", timeout=5.0)
                results[svc_name] = {"status": "ok", "url": url} if resp.status_code == 200 else {"status": "unhealthy", "url": url}
            except Exception:
                results[svc_name] = {"status": "unreachable", "url": url}
        return {"mode": "proxy", "services": results}

    # ─── Mode-dependent routing ──────────────────────────────
    if settings.GATEWAY_MODE == "monolith":
        _register_monolith_routers(app)
    else:
        proxy.build_routes()
        _register_proxy_routes(app, proxy.routes)

    return app


def _register_monolith_routers(app: FastAPI):
    """Import and register routers directly (monolith mode)."""
    # Simplified for now - only auth service
    try:
        from services.auth.router import router as auth_router
        app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
    except ImportError:
        pass


def _register_proxy_routes(app: FastAPI, routes: dict[str, str]):
    """Register catch-all routes that proxy to downstream services."""
    for prefix, target in routes.items():
        _add_proxy_route(app, prefix, target)


def _add_proxy_route(app: FastAPI, prefix: str, target: str):
    """Add catch-all routes for a specific service prefix."""
    tag = prefix.replace("/api/", "").capitalize()

    async def _forward(request: Request, _target: str = target) -> Response:
        return await proxy.forward(request, _target)

    app.add_api_route(
        prefix,
        _forward,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        tags=[tag],
        name=f"proxy_{tag.lower()}_root",
    )

    async def _forward_sub(request: Request, path: str, _target: str = target) -> Response:
        return await proxy.forward(request, _target)

    app.add_api_route(
        f"{prefix}/{{path:path}}",
        _forward_sub,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        tags=[tag],
        name=f"proxy_{tag.lower()}_sub",
    )


app = create_app()

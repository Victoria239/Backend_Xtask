"""Shared middleware for the application."""

import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shared.exceptions import AppException
from shared.logging import get_logger

logger = get_logger(__name__)

# ─── Request ID context var (accessible from anywhere) ──────────
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get()


# ─── Request ID Middleware ───────────────────────────────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request ID to every incoming request.
    
    - Reads X-Request-ID header if present, otherwise generates a UUID.
    - Stores it in a ContextVar so loggers and services can access it.
    - Returns it in the X-Request-ID response header for tracing.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_ctx.set(rid)
        request.state.request_id = rid

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


# ─── Request Logging Middleware ──────────────────────────────────
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "http_request",
            request_id=get_request_id(),
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


# ─── Global Exception Handlers ──────────────────────────────────
def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app.
    
    Catches:
    - AppException (our custom hierarchy) → structured JSON
    - Unhandled exceptions → 500 with request_id for debugging
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        rid = get_request_id()
        logger.warning(
            "app_exception",
            request_id=rid,
            status=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "request_id": rid,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = get_request_id()
        logger.error(
            "unhandled_exception",
            request_id=rid,
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "request_id": rid,
            },
        )

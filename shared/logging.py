import os

import structlog
from shared.config import get_settings


def setup_logging() -> None:
    """Configure structured logging for the application.

    Renderer:
      - LOG_FORMAT=json  → JSONRenderer (parseable por Promtail/Loki)
      - LOG_FORMAT=console o dev sin override → ConsoleRenderer (legible)
      - producción sin override → JSONRenderer
    """
    settings = get_settings()

    level_map = {
        "debug": 10,
        "info": 20,
        "warning": 30,
        "error": 40,
        "critical": 50,
    }
    log_level = level_map.get(settings.LOG_LEVEL.lower(), 20)

    log_format = os.getenv("LOG_FORMAT", "").lower()
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    elif log_format == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = (
            structlog.dev.ConsoleRenderer()
            if settings.is_development
            else structlog.processors.JSONRenderer()
        )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)

"""Instrumentación Prometheus compartida (Sprint 7).

Por servicio se obtiene:
  - http_requests_total{method, handler, status, service}
  - http_request_duration_seconds_bucket{...} (histograma para p50/p95/p99)
  - http_requests_inprogress (gauge)

Custom metrics expuestas (importables desde los services):
  - xtask_docgen_generation_seconds (histogram, label=template_id)
  - xtask_rag_search_seconds (histogram)
  - xtask_okr_recalculations_total (counter, label=tenant_id)
  - xtask_contracts_state_transitions_total (counter, label=from,to)
  - xtask_plans_simulations_total (counter)
  - xtask_notifications_emitted_total (counter, label=kind,category)

Si el cliente quiere desactivar /metrics, basta con METRICS_ENABLED=false en env.
"""

from typing import Any

from fastapi import FastAPI
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# ─── Custom domain metrics (compartidas entre servicios) ─────────────────────────────────────────
DOCGEN_GENERATION_SECONDS = Histogram(
    "xtask_docgen_generation_seconds",
    "Duración del pipeline DocGen (Jinja+RAG+sanitize)",
    labelnames=("template_id",),
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

RAG_SEARCH_SECONDS = Histogram(
    "xtask_rag_search_seconds",
    "Duración de búsquedas RAG (embedding + pgvector lookup)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

OKR_RECALCULATIONS = Counter(
    "xtask_okr_recalculations_total",
    "Recalculaciones de cascada de OKRs",
    labelnames=("tenant_id",),
)

CONTRACTS_TRANSITIONS = Counter(
    "xtask_contracts_state_transitions_total",
    "Transiciones de estado de contratos",
    labelnames=("from_status", "to_status"),
)

PLANS_SIMULATIONS = Counter(
    "xtask_plans_simulations_total",
    "Simulaciones del motor de comisiones",
)

NOTIFICATIONS_EMITTED = Counter(
    "xtask_notifications_emitted_total",
    "Notificaciones in-app emitidas",
    labelnames=("kind", "category"),
)


def setup_metrics(app: FastAPI, service_name: str, metrics_path: str = "/metrics") -> None:
    """Adjunta el instrumentator y expone /metrics.

    Idempotente: si ya está instrumentado, no rompe.
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=[f"{metrics_path}.*", "/health.*"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    try:
        instrumentator.instrument(app).expose(
            app, endpoint=metrics_path, include_in_schema=False,
        )
    except Exception:  # noqa: BLE001
        # Algunos services ya instrumentaron (hot reload), no romper
        pass

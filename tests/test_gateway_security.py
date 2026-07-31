"""Tests de seguridad del gateway (Sprint 7 bug bash).

Cubre el fix crítico que el bug bash encontró: el gateway no debe rutear
`/api/*/internal/*` al microservicio destino.

Requiere stack levantado en localhost.
"""

import os

import httpx
import pytest

# Cuando se corre dentro del docker network, gateway es resoluble como hostname.
# Desde fuera (host shell), apunta a localhost:8001.
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8000")


@pytest.fixture(scope="module")
async def gateway_available():
    async with httpx.AsyncClient(timeout=3.0) as c:
        # El gateway monta health en /api/health, no en /health raíz
        try:
            r = await c.get(f"{GATEWAY_URL}/api/health")
            if r.status_code != 200:
                pytest.skip(f"gateway no respondió 200 (status={r.status_code})")
        except (httpx.RequestError, httpx.TimeoutException):
            pytest.skip("gateway no reachable")
    yield True


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/contracts/internal/scan-expiry",
    "/api/docgen/internal/generate",
    "/api/okrs/internal/kpi-checkin",
    "/api/contracts/internal/something-future",  # path nuevo que no exista todavía
])
async def test_gateway_blocks_internal_paths(gateway_available, path):
    """Bug crítico que arreglamos: el gateway expone endpoints internos sin auth."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        resp = await c.post(f"{GATEWAY_URL}{path}")
    # Gateway debe responder 404 ANTES de rutear al service.
    assert resp.status_code == 404, \
        f"{path} no fue bloqueado por el gateway (status={resp.status_code})"


@pytest.mark.asyncio
async def test_gateway_routes_normal_paths(gateway_available):
    """El bloqueo del /internal/ no debe romper rutas normales — solo deben pedir auth."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        # GET a una ruta que requiere auth — debe responder 401, no 404
        resp = await c.get(f"{GATEWAY_URL}/api/contracts/")
    assert resp.status_code in (401, 403), \
        f"esperaba 401/403 (sin token), vino {resp.status_code}"


@pytest.mark.asyncio
async def test_gateway_health_works(gateway_available):
    """Health del gateway debe responder sin auth."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        resp = await c.get(f"{GATEWAY_URL}/api/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_scan_expiry_requires_auth(gateway_available):
    """El endpoint público scan-expiry (no /internal/) requiere admin."""
    async with httpx.AsyncClient(timeout=5.0) as c:
        resp = await c.post(f"{GATEWAY_URL}/api/contracts/scan-expiry")
    assert resp.status_code in (401, 403), \
        f"esperaba 401/403 sin auth, vino {resp.status_code}"

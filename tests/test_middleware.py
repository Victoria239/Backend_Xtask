"""Tests for middleware: Request ID and Global Exception Handler."""

import pytest


class TestRequestIdMiddleware:
    """Verify X-Request-ID is generated and returned."""

    async def test_generates_request_id(self, client):
        r = await client.get("/api/health")
        assert "x-request-id" in r.headers
        assert len(r.headers["x-request-id"]) > 0

    async def test_preserves_provided_request_id(self, client):
        custom_id = "my-custom-request-id-123"
        r = await client.get("/api/health", headers={"X-Request-ID": custom_id})
        assert r.headers["x-request-id"] == custom_id

    async def test_unique_ids_per_request(self, client):
        r1 = await client.get("/api/health")
        r2 = await client.get("/api/health")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


class TestGlobalExceptionHandler:
    """Verify structured error responses."""

    async def test_health_ok(self, client):
        r = await client.get("/api/health")
        assert r.status_code == 200

    async def test_401_missing_token(self, client):
        r = await client.get("/api/proyectos")
        assert r.status_code == 401
        body = r.json()
        assert body["success"] is False
        assert "request_id" in body

    async def test_401_invalid_token(self, client):
        r = await client.get(
            "/api/proyectos", headers={"Authorization": "Bearer invalid"}
        )
        assert r.status_code == 401
        body = r.json()
        assert body["success"] is False
        assert "request_id" in body

    async def test_error_includes_request_id(self, client):
        r = await client.get("/api/proyectos")
        body = r.json()
        assert body["request_id"] == r.headers["x-request-id"]

"""Tests for pagination across all list endpoints."""

import pytest

from tests.conftest import auth_header, ADMIN_TOKEN


PAGINATED_ENDPOINTS = [
    "/api/proyectos",
    "/api/empleados",
    "/api/finanzas/presupuestos",
    "/api/finanzas/facturas",
    "/api/nominas",
    "/api/kpis",
    "/api/habilidades",
]


class TestPaginationStructure:
    """All list endpoints return paginated response format."""

    @pytest.mark.parametrize("endpoint", PAGINATED_ENDPOINTS)
    async def test_returns_pagination_meta(self, client, endpoint):
        r = await client.get(endpoint, headers=auth_header(ADMIN_TOKEN))
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert "pagination" in body
        pag = body["pagination"]
        assert "page" in pag
        assert "pageSize" in pag
        assert "total" in pag
        assert "totalPages" in pag

    @pytest.mark.parametrize("endpoint", PAGINATED_ENDPOINTS)
    async def test_default_page_size_is_20(self, client, endpoint):
        r = await client.get(endpoint, headers=auth_header(ADMIN_TOKEN))
        assert r.json()["pagination"]["pageSize"] == 20

    @pytest.mark.parametrize("endpoint", PAGINATED_ENDPOINTS)
    async def test_custom_page_size(self, client, endpoint):
        r = await client.get(
            endpoint, params={"pageSize": 2}, headers=auth_header(ADMIN_TOKEN)
        )
        assert r.json()["pagination"]["pageSize"] == 2

    async def test_page_size_max_100(self, client):
        r = await client.get(
            "/api/proyectos",
            params={"pageSize": 200},
            headers=auth_header(ADMIN_TOKEN),
        )
        assert r.status_code == 422  # validation error

    async def test_page_min_1(self, client):
        r = await client.get(
            "/api/proyectos",
            params={"page": 0},
            headers=auth_header(ADMIN_TOKEN),
        )
        assert r.status_code == 422


class TestPaginationLogic:
    """Pagination returns correct slices."""

    async def test_page_2_offset(self, client):
        r = await client.get(
            "/api/proyectos",
            params={"pageSize": 1, "page": 1},
            headers=auth_header(ADMIN_TOKEN),
        )
        body = r.json()
        total = body["pagination"]["total"]
        page1_data = body["data"]

        if total > 1:
            r2 = await client.get(
                "/api/proyectos",
                params={"pageSize": 1, "page": 2},
                headers=auth_header(ADMIN_TOKEN),
            )
            page2_data = r2.json()["data"]
            assert page1_data[0]["id"] != page2_data[0]["id"]

    async def test_total_pages_calculation(self, client):
        r = await client.get(
            "/api/proyectos",
            params={"pageSize": 2},
            headers=auth_header(ADMIN_TOKEN),
        )
        pag = r.json()["pagination"]
        import math
        expected_pages = math.ceil(pag["total"] / pag["pageSize"]) if pag["total"] > 0 else 0
        assert pag["totalPages"] == expected_pages

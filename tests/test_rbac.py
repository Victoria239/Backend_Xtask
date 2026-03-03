"""Tests for Role-Based Access Control (RBAC)."""

import pytest

from tests.conftest import auth_header, ADMIN_TOKEN, MANAGER_TOKEN, USER_TOKEN


class TestRBACReadAccess:
    """All authenticated users (user, manager, admin) can read."""

    @pytest.mark.parametrize("token", [USER_TOKEN, MANAGER_TOKEN, ADMIN_TOKEN])
    async def test_any_role_can_list_projects(self, client, token):
        r = await client.get("/api/proyectos", headers=auth_header(token))
        assert r.status_code == 200

    @pytest.mark.parametrize("token", [USER_TOKEN, MANAGER_TOKEN, ADMIN_TOKEN])
    async def test_any_role_can_list_employees(self, client, token):
        r = await client.get("/api/empleados", headers=auth_header(token))
        assert r.status_code == 200

    @pytest.mark.parametrize("token", [USER_TOKEN, MANAGER_TOKEN, ADMIN_TOKEN])
    async def test_any_role_can_list_kpis(self, client, token):
        r = await client.get("/api/kpis", headers=auth_header(token))
        assert r.status_code == 200


class TestRBACManagerAccess:
    """Only admin and manager can create/update resources."""

    async def test_user_cannot_create_project(self, client):
        r = await client.post(
            "/api/proyectos",
            json={"name": "RBAC test", "status": "active"},
            headers=auth_header(USER_TOKEN),
        )
        assert r.status_code == 403
        assert "not authorized" in r.json()["error"].lower()

    async def test_manager_can_create_project(self, client):
        r = await client.post(
            "/api/proyectos",
            json={"name": "Manager RBAC test", "status": "active"},
            headers=auth_header(MANAGER_TOKEN),
        )
        assert r.status_code == 200
        pid = r.json()["data"]["id"] if "data" in r.json() else r.json()["id"]
        # Cleanup
        await client.delete(f"/api/proyectos/{pid}", headers=auth_header(ADMIN_TOKEN))

    async def test_user_cannot_create_payroll(self, client):
        r = await client.post(
            "/api/nominas",
            json={"employee_id": 1, "period": "2026-03", "base_salary": 1000, "bonuses": 0, "deductions": 0},
            headers=auth_header(USER_TOKEN),
        )
        assert r.status_code == 403


class TestRBACAdminAccess:
    """Only admin can delete resources."""

    async def test_manager_cannot_delete_project(self, client):
        # Create first
        r = await client.post(
            "/api/proyectos",
            json={"name": "Delete RBAC test", "status": "active"},
            headers=auth_header(ADMIN_TOKEN),
        )
        pid = r.json()["data"]["id"] if "data" in r.json() else r.json()["id"]

        # Manager tries to delete
        r = await client.delete(f"/api/proyectos/{pid}", headers=auth_header(MANAGER_TOKEN))
        assert r.status_code == 403

        # Admin can delete
        r = await client.delete(f"/api/proyectos/{pid}", headers=auth_header(ADMIN_TOKEN))
        assert r.status_code == 204

    async def test_user_cannot_delete_employee(self, client):
        r = await client.delete("/api/empleados/999", headers=auth_header(USER_TOKEN))
        assert r.status_code == 403

    async def test_user_cannot_validate_kpi(self, client):
        r = await client.patch(
            "/api/kpis/999/validar",
            json={"validated": True},
            headers=auth_header(USER_TOKEN),
        )
        assert r.status_code == 403

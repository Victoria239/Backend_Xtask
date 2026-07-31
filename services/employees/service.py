"""Employees service - Business logic."""

from shared.builders import ResponseBuilder
from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from services.employees.repository import EmployeeRepository
from services.employees.schemas import (
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeDocumentOut,
    EmployeeUpdate,
    EmployeeOut,
    OrgNode,
)


class EmployeeService:
    def __init__(self, repo: EmployeeRepository):
        self.repo = repo

    async def list_employees_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return (
            ResponseBuilder()
            .with_items(items, EmployeeOut)
            .with_pagination(total=total, page=page, page_size=page_size)
            .with_filters(filters)
            .build()
        )

    async def get_employee(self, employee_id: int) -> EmployeeOut:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        return EmployeeOut.model_validate(employee)

    async def create_employee(self, data: EmployeeCreate, tenant_id: int | None = None) -> EmployeeOut:
        payload = data.model_dump()
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id
        employee = await self.repo.create(payload)

        try:
            from shared.n8n_client import emit_event
            await emit_event("xtask.employee.created", {
                "tenant_id": tenant_id or payload.get("tenant_id"),
                "employee_id": employee.id,
                "name": f"{employee.first_name} {employee.last_name}",
                "department": employee.department,
                "position": employee.position,
                "hire_date": str(employee.hire_date) if employee.hire_date else None,
            })
        except Exception:  # noqa: BLE001
            pass

        return EmployeeOut.model_validate(employee)

    async def update_employee(self, employee_id: int, data: EmployeeUpdate) -> EmployeeOut:
        employee = await self.repo.update(employee_id, data.model_dump(exclude_unset=True))
        if not employee:
            raise NotFoundException("Employee", employee_id)
        return EmployeeOut.model_validate(employee)

    async def delete_employee(self, employee_id: int) -> None:
        deleted = await self.repo.delete(employee_id)
        if not deleted:
            raise NotFoundException("Employee", employee_id)

    async def assign_projects(self, employee_id: int, project_ids: list[int]) -> dict:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        await self.repo.assign_projects(employee_id, project_ids)
        return {"success": True, "employee_id": employee_id, "project_ids": project_ids}

    async def get_project_ids(self, employee_id: int) -> list[int]:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        return await self.repo.get_project_ids(employee_id)

    # ─── H-01: org chart ─────────────────────────────────────
    async def get_org_chart(self, tenant_id: int | None = None) -> list[OrgNode]:
        employees = await self.repo.list_for_org_chart(tenant_id=tenant_id)
        nodes: dict[int, OrgNode] = {}
        for e in employees:
            full_name = " ".join(filter(None, [e.first_name, e.last_name])) or f"Empleado #{e.id}"
            nodes[e.id] = OrgNode(
                id=e.id,
                full_name=full_name,
                position=e.position,
                department=e.department,
                manager_id=e.manager_id,
                reports=[],
            )
        roots: list[OrgNode] = []
        for node in nodes.values():
            parent = nodes.get(node.manager_id) if node.manager_id else None
            if parent:
                parent.reports.append(node)
            else:
                roots.append(node)
        return roots

    # ─── H-01: employee documents ───────────────────────────
    async def add_document(
        self, employee_id: int, data: EmployeeDocumentCreate, tenant_id: int | None
    ) -> EmployeeDocumentOut:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        doc = await self.repo.add_document(
            employee_id=employee_id, tenant_id=tenant_id, **data.model_dump()
        )
        return EmployeeDocumentOut.model_validate(doc)

    async def list_documents(self, employee_id: int) -> list[EmployeeDocumentOut]:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        docs = await self.repo.list_documents(employee_id)
        return [EmployeeDocumentOut.model_validate(d) for d in docs]

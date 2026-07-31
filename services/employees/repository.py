"""Employees service - Database repository."""

from typing import Any

from sqlalchemy import select, delete

from services.employees.models import Employee, EmployeeDocument, EmployeeProject
from shared.repository import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee

    def _apply_filters(self, query, filters: dict[str, Any] | None = None):
        """Support search by name and custom filter keys."""
        if filters:
            if filters.get("department"):
                query = query.where(Employee.department == filters["department"])
            if filters.get("contract_status"):
                query = query.where(Employee.contract_status == filters["contract_status"])
            if filters.get("search"):
                search = f"%{filters['search']}%"
                query = query.where(
                    (Employee.first_name.ilike(search)) | (Employee.last_name.ilike(search))
                )
        return query

    async def get_by_user_id(self, user_id: int) -> Employee | None:
        result = await self.db.execute(select(Employee).where(Employee.user_id == user_id))
        return result.scalar_one_or_none()

    async def delete(self, entity_id: int) -> bool:
        """Override to cascade-delete project assignments."""
        employee = await self.get_by_id(entity_id)
        if not employee:
            return False
        await self.db.execute(
            delete(EmployeeProject).where(EmployeeProject.employee_id == entity_id)
        )
        await self.db.delete(employee)
        await self.db.flush()
        return True

    async def assign_projects(self, employee_id: int, project_ids: list[int]) -> None:
        await self.db.execute(
            delete(EmployeeProject).where(EmployeeProject.employee_id == employee_id)
        )
        for project_id in project_ids:
            assignment = EmployeeProject(employee_id=employee_id, project_id=project_id)
            self.db.add(assignment)
        await self.db.flush()

    async def get_project_ids(self, employee_id: int) -> list[int]:
        result = await self.db.execute(
            select(EmployeeProject.project_id).where(EmployeeProject.employee_id == employee_id)
        )
        return list(result.scalars().all())

    # ─── H-01: org chart ────────────────────────────────────
    async def list_for_org_chart(self, tenant_id: int | None = None) -> list[Employee]:
        stmt = select(Employee)
        if tenant_id is not None:
            stmt = stmt.where(Employee.tenant_id == tenant_id)
        stmt = stmt.where(Employee.contract_status == "active")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ─── H-01: employee documents ──────────────────────────
    async def add_document(self, employee_id: int, tenant_id: int | None, **fields) -> EmployeeDocument:
        doc = EmployeeDocument(employee_id=employee_id, tenant_id=tenant_id, **fields)
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def list_documents(self, employee_id: int) -> list[EmployeeDocument]:
        result = await self.db.execute(
            select(EmployeeDocument)
            .where(EmployeeDocument.employee_id == employee_id)
            .order_by(EmployeeDocument.created_at.desc())
        )
        return list(result.scalars().all())

"""Employees service - Database repository."""

from typing import Any

from sqlalchemy import select, delete

from services.employees.models import Employee, EmployeeProject
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

"""Employees service - Business logic."""

from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from services.employees.repository import EmployeeRepository
from services.employees.schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut


class EmployeeService:
    def __init__(self, repo: EmployeeRepository):
        self.repo = repo

    async def list_employees(self, filters: dict | None = None) -> list[EmployeeOut]:
        employees = await self.repo.get_all(filters)
        return [EmployeeOut.model_validate(e) for e in employees]

    async def list_employees_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return PaginatedResponse.create(
            items=[EmployeeOut.model_validate(e) for e in items],
            total=total, page=page, page_size=page_size,
        )

    async def get_employee(self, employee_id: int) -> EmployeeOut:
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise NotFoundException("Employee", employee_id)
        return EmployeeOut.model_validate(employee)

    async def create_employee(self, data: EmployeeCreate) -> EmployeeOut:
        employee = await self.repo.create(data.model_dump())
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

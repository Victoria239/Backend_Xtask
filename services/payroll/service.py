"""Payroll service - Business logic."""

from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from services.payroll.repository import PayrollRepository
from services.payroll.schemas import PayrollCreate, PayrollUpdate, PayrollOut


class PayrollService:
    def __init__(self, repo: PayrollRepository):
        self.repo = repo

    async def list_payrolls_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return PaginatedResponse.create(
            items=[PayrollOut.model_validate(p) for p in items],
            total=total, page=page, page_size=page_size,
        )

    async def get_payroll(self, payroll_id: int) -> PayrollOut:
        payroll = await self.repo.get_by_id(payroll_id)
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        return PayrollOut.model_validate(payroll)

    async def create_payroll(self, data: PayrollCreate) -> PayrollOut:
        net_salary = data.base_salary + data.bonuses - data.deductions
        payroll_data = data.model_dump()
        payroll_data["net_salary"] = net_salary
        payroll = await self.repo.create(payroll_data)
        return PayrollOut.model_validate(payroll)

    async def update_payroll(self, payroll_id: int, data: PayrollUpdate) -> PayrollOut:
        payroll = await self.repo.update(payroll_id, data.model_dump(exclude_unset=True))
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        return PayrollOut.model_validate(payroll)

    async def change_status(self, payroll_id: int, status: str) -> PayrollOut:
        payroll = await self.repo.update_status(payroll_id, status)
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        return PayrollOut.model_validate(payroll)

    async def delete_payroll(self, payroll_id: int) -> None:
        deleted = await self.repo.delete(payroll_id)
        if not deleted:
            raise NotFoundException("Payroll", payroll_id)

    async def get_metrics(self, filters: dict | None = None) -> dict:
        return await self.repo.get_metrics(filters)

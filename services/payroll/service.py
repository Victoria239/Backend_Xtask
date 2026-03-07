"""Payroll service - Business logic."""

from shared.builders import ResponseBuilder
from shared.exceptions import NotFoundException
from shared.schemas import PaginatedResponse
from shared.state_machine import PAYROLL_STATES
from shared.strategies import SalaryStrategy, StandardSalaryStrategy
from shared.validators import PositiveAmountValidator, RequiredFieldsValidator, build_chain
from services.payroll.repository import PayrollRepository
from services.payroll.schemas import PayrollCreate, PayrollUpdate, PayrollOut

# ─── Validation chain for payroll creation ─────────────────────────
_create_chain = build_chain(
    RequiredFieldsValidator(["employee_id", "period", "base_salary"]),
    PositiveAmountValidator("base_salary"),
)


class PayrollService:
    def __init__(
        self,
        repo: PayrollRepository,
        salary_strategy: SalaryStrategy | None = None,
    ):
        self.repo = repo
        self._salary_strategy = salary_strategy or StandardSalaryStrategy()

    async def list_payrolls_paginated(
        self, filters: dict | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        items, total = await self.repo.get_paginated(page, page_size, filters)
        return (
            ResponseBuilder()
            .with_items(items, PayrollOut)
            .with_pagination(total=total, page=page, page_size=page_size)
            .with_filters(filters)
            .build()
        )

    async def get_payroll(self, payroll_id: int) -> PayrollOut:
        payroll = await self.repo.get_by_id(payroll_id)
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        return PayrollOut.model_validate(payroll)

    async def create_payroll(self, data: PayrollCreate) -> PayrollOut:
        await _create_chain.validate(data.model_dump())
        net_salary = self._salary_strategy.calculate_net(
            data.base_salary, data.bonuses, data.deductions,
        )
        payroll_data = data.model_dump()
        payroll_data["net_salary"] = net_salary
        payroll = await self.repo.create(payroll_data)
        return PayrollOut.model_validate(payroll)

    async def update_payroll(self, payroll_id: int, data: PayrollUpdate) -> PayrollOut:
        payroll = await self.repo.update(payroll_id, data.model_dump(exclude_unset=True))
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        return PayrollOut.model_validate(payroll)

    async def change_status(self, payroll_id: int, new_status: str) -> PayrollOut:
        payroll = await self.repo.get_by_id(payroll_id)
        if not payroll:
            raise NotFoundException("Payroll", payroll_id)
        PAYROLL_STATES.validate_transition(payroll.status, new_status)
        updated = await self.repo.update_status(payroll_id, new_status)
        return PayrollOut.model_validate(updated)

    async def delete_payroll(self, payroll_id: int) -> None:
        deleted = await self.repo.delete(payroll_id)
        if not deleted:
            raise NotFoundException("Payroll", payroll_id)

    async def get_metrics(self, filters: dict | None = None) -> dict:
        return await self.repo.get_metrics(filters)

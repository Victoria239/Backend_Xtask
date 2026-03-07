"""Strategy Pattern — Pluggable business-logic strategies.

Strategies encapsulate algorithms that can be swapped at runtime
without modifying the service classes that use them.

Usage:
    service = PayrollService(repo, salary_strategy=ColombianSalaryStrategy())
"""

from abc import ABC, abstractmethod
from typing import Any


# ─── Salary Calculation Strategies ────────────────────────────────

class SalaryStrategy(ABC):
    """Base strategy for net salary calculation."""

    @abstractmethod
    def calculate_net(self, base_salary: float, bonuses: float, deductions: float) -> float:
        """Calculate the net salary given base, bonuses, and deductions."""
        ...


class StandardSalaryStrategy(SalaryStrategy):
    """Default: net = base + bonuses - deductions."""

    def calculate_net(self, base_salary: float, bonuses: float, deductions: float) -> float:
        return base_salary + bonuses - deductions


class ColombianSalaryStrategy(SalaryStrategy):
    """Colombian labor law: includes mandatory health (4%) and pension (4%) deductions."""

    HEALTH_RATE = 0.04
    PENSION_RATE = 0.04

    def calculate_net(self, base_salary: float, bonuses: float, deductions: float) -> float:
        mandatory = base_salary * (self.HEALTH_RATE + self.PENSION_RATE)
        return base_salary + bonuses - deductions - mandatory


class ContractorSalaryStrategy(SalaryStrategy):
    """Contractor: no mandatory deductions, flat tax withholding."""

    WITHHOLDING_RATE = 0.11

    def calculate_net(self, base_salary: float, bonuses: float, deductions: float) -> float:
        withholding = (base_salary + bonuses) * self.WITHHOLDING_RATE
        return base_salary + bonuses - deductions - withholding


# ─── Budget Execution Strategies ──────────────────────────────────

class ExecutionStrategy(ABC):
    """Base strategy for budget execution calculation."""

    @abstractmethod
    def calculate(self, total_amount: float, spent_amount: float) -> dict[str, Any]:
        """Return execution metrics for a budget."""
        ...


class StandardExecutionStrategy(ExecutionStrategy):
    """Default execution: simple percentage calculation."""

    def calculate(self, total_amount: float, spent_amount: float) -> dict[str, Any]:
        remaining = total_amount - spent_amount
        percentage = (spent_amount / total_amount * 100) if total_amount > 0 else 0
        return {
            "total_amount": total_amount,
            "spent_amount": spent_amount,
            "remaining_amount": remaining,
            "execution_percentage": round(percentage, 2),
        }


class AlertExecutionStrategy(ExecutionStrategy):
    """Execution with alert thresholds (>80% warning, >95% critical)."""

    WARNING_THRESHOLD = 80.0
    CRITICAL_THRESHOLD = 95.0

    def calculate(self, total_amount: float, spent_amount: float) -> dict[str, Any]:
        remaining = total_amount - spent_amount
        percentage = (spent_amount / total_amount * 100) if total_amount > 0 else 0
        rounded = round(percentage, 2)

        if rounded >= self.CRITICAL_THRESHOLD:
            alert = "critical"
        elif rounded >= self.WARNING_THRESHOLD:
            alert = "warning"
        else:
            alert = "normal"

        return {
            "total_amount": total_amount,
            "spent_amount": spent_amount,
            "remaining_amount": remaining,
            "execution_percentage": rounded,
            "alert_level": alert,
        }

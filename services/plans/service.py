"""Plans service — business logic + motor de evaluación (C-03)."""

import logging
from typing import Any

from services.plans.jsonlogic import JsonLogicError, evaluate
from services.plans.models import CommissionPlan, PlanRule
from services.plans.repository import PlanRepository
from services.plans.schemas import (
    PlanDetail,
    PlanIn,
    PlanSummary,
    PlanUpdate,
    RuleIn,
    RuleOut,
    RuleTrace,
    SimulateRequest,
    SimulateResponse,
)

logger = logging.getLogger(__name__)


def _plan_summary(plan: CommissionPlan, rule_count: int) -> PlanSummary:
    base = PlanSummary.model_validate(plan).model_dump()
    base["rule_count"] = rule_count
    return PlanSummary(**base)


def _plan_detail(plan: CommissionPlan, rules: list[PlanRule]) -> PlanDetail:
    base = PlanDetail.model_validate(plan).model_dump()
    base["rules"] = [RuleOut.model_validate(r) for r in rules]
    return PlanDetail(**base)


class PlanService:
    def __init__(self, repo: PlanRepository):
        self.repo = repo

    # ─── CRUD planes ─────────────────────────────────────────
    async def list_plans(self, tenant_id: int, active: bool | None = None) -> list[PlanSummary]:
        items = await self.repo.list_plans(tenant_id, active)
        return [_plan_summary(p, rc) for p, rc in items]

    async def get_plan_detail(self, tenant_id: int, plan_id: int) -> PlanDetail | None:
        plan = await self.repo.get_plan(tenant_id, plan_id)
        if not plan:
            return None
        rules = await self.repo.list_rules(plan_id)
        return _plan_detail(plan, rules)

    async def create_plan(
        self, tenant_id: int, user_id: int | None, payload: PlanIn
    ) -> PlanDetail:
        data = payload.model_dump(exclude={"rules"})
        data["tenant_id"] = tenant_id
        data["created_by"] = user_id
        plan = await self.repo.create_plan(**data)

        # Validar reglas con un dry-run del evaluador antes de persistir
        for r in payload.rules:
            self._validate_rule(r)
            await self.repo.create_rule(
                tenant_id=tenant_id, plan_id=plan.id, **r.model_dump()
            )
        detail = await self.get_plan_detail(tenant_id, plan.id)
        if detail is None:
            raise RuntimeError(f"Plan {plan.id} desapareció inmediatamente después de crearlo (race?)")
        return detail

    async def update_plan(
        self, tenant_id: int, plan_id: int, payload: PlanUpdate
    ) -> PlanDetail | None:
        plan = await self.repo.get_plan(tenant_id, plan_id)
        if not plan:
            return None
        await self.repo.update_plan(plan, **payload.model_dump(exclude_unset=True))
        return await self.get_plan_detail(tenant_id, plan.id)

    async def delete_plan(self, tenant_id: int, plan_id: int) -> bool:
        plan = await self.repo.get_plan(tenant_id, plan_id)
        if not plan:
            return False
        await self.repo.delete_plan(plan)
        return True

    # ─── CRUD reglas ─────────────────────────────────────────
    async def add_rule(self, tenant_id: int, plan_id: int, payload: RuleIn) -> RuleOut:
        plan = await self.repo.get_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} no existe en este tenant")
        self._validate_rule(payload)
        rule = await self.repo.create_rule(
            tenant_id=tenant_id, plan_id=plan_id, **payload.model_dump()
        )
        return RuleOut.model_validate(rule)

    async def update_rule(self, tenant_id: int, rule_id: int, payload: RuleIn) -> RuleOut | None:
        rule = await self.repo.get_rule(tenant_id, rule_id)
        if not rule:
            return None
        self._validate_rule(payload)
        await self.repo.update_rule(rule, **payload.model_dump())
        return RuleOut.model_validate(rule)

    async def delete_rule(self, tenant_id: int, rule_id: int) -> bool:
        rule = await self.repo.get_rule(tenant_id, rule_id)
        if not rule:
            return False
        await self.repo.delete_rule(rule)
        return True

    def _validate_rule(self, r: RuleIn) -> None:
        """Sanity check: evaluamos `when` y `amount` con dict vacío. Si lanza JsonLogicError, error de sintaxis."""
        try:
            evaluate(r.when, {})
        except JsonLogicError as e:
            raise ValueError(f"Condición inválida en regla '{r.label}': {e}") from e
        try:
            evaluate(r.amount, {})
        except JsonLogicError as e:
            raise ValueError(f"Cálculo inválido en regla '{r.label}': {e}") from e

    # ─── Motor de evaluación ─────────────────────────────────────────
    async def simulate(
        self, tenant_id: int, user_id: int | None, plan_id: int, payload: SimulateRequest
    ) -> SimulateResponse:
        try:
            from shared.metrics import PLANS_SIMULATIONS
            PLANS_SIMULATIONS.inc()
        except Exception:  # noqa: BLE001
            pass
        plan = await self.repo.get_plan(tenant_id, plan_id)
        if not plan:
            raise ValueError("Plan no encontrado")
        rules = await self.repo.list_rules(plan_id)

        # Mezclar defaults del plan + contexto pasado
        ctx: dict[str, Any] = {**(plan.defaults or {}), **payload.context}

        traces: list[RuleTrace] = []
        total = 0.0
        matched = 0

        for rule in rules:
            try:
                cond_result = evaluate(rule.when, ctx)
            except JsonLogicError as e:
                traces.append(RuleTrace(rule_id=rule.id, label=rule.label, matched=False, error=f"when: {e}"))
                continue

            is_match = bool(cond_result)
            if not is_match:
                traces.append(RuleTrace(rule_id=rule.id, label=rule.label, matched=False))
                continue

            try:
                amount = float(evaluate(rule.amount, ctx))
            except (JsonLogicError, TypeError, ValueError) as e:
                traces.append(RuleTrace(rule_id=rule.id, label=rule.label, matched=True, error=f"amount: {e}"))
                continue

            matched += 1
            traces.append(RuleTrace(rule_id=rule.id, label=rule.label, matched=True, amount=amount))
            total += amount

            if plan.strategy == "first-match":
                break

        # Persistir simulación para auditoría
        try:
            await self.repo.record_simulation(
                tenant_id=tenant_id, plan_id=plan_id,
                employee_id=payload.employee_id, context=ctx,
                result_amount=total,
                trace=[t.model_dump() for t in traces],
                created_by=user_id,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("plan_simulation_persist_failed", exc_info=e)

        return SimulateResponse(
            plan_id=plan.id,
            plan_name=plan.name,
            strategy=plan.strategy,
            currency=plan.currency,
            total_amount=round(total, 2),
            matched_rules=matched,
            trace=traces,
            context=ctx,
        )

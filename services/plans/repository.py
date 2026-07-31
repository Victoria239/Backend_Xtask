"""Plans service — DB repository (C-03)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.plans.models import CommissionPlan, PlanRule, PlanSimulation


class PlanRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_plans(self, tenant_id: int, active: bool | None = None) -> list[tuple[CommissionPlan, int]]:
        """Devuelve (plan, rule_count)."""
        stmt = (
            select(CommissionPlan, func.count(PlanRule.id).label("rc"))
            .outerjoin(PlanRule, PlanRule.plan_id == CommissionPlan.id)
            .where(CommissionPlan.tenant_id == tenant_id)
            .group_by(CommissionPlan.id)
            .order_by(CommissionPlan.created_at.desc())
        )
        if active is not None:
            stmt = stmt.where(CommissionPlan.active == active)
        rows = (await self.db.execute(stmt)).all()
        return [(r[0], int(r[1] or 0)) for r in rows]

    async def get_plan(self, tenant_id: int, plan_id: int) -> CommissionPlan | None:
        stmt = select(CommissionPlan).where(
            CommissionPlan.tenant_id == tenant_id, CommissionPlan.id == plan_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_plan(self, **kwargs) -> CommissionPlan:
        plan = CommissionPlan(**kwargs)
        self.db.add(plan)
        await self.db.flush()
        return plan

    async def update_plan(self, plan: CommissionPlan, **kwargs) -> CommissionPlan:
        for k, v in kwargs.items():
            if v is not None:
                setattr(plan, k, v)
        await self.db.flush()
        return plan

    async def delete_plan(self, plan: CommissionPlan) -> None:
        await self.db.delete(plan)
        await self.db.flush()

    async def list_rules(self, plan_id: int) -> list[PlanRule]:
        stmt = (
            select(PlanRule)
            .where(PlanRule.plan_id == plan_id)
            .order_by(PlanRule.priority.asc(), PlanRule.id.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_rule(self, tenant_id: int, rule_id: int) -> PlanRule | None:
        stmt = select(PlanRule).where(PlanRule.tenant_id == tenant_id, PlanRule.id == rule_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_rule(self, **kwargs) -> PlanRule:
        rule = PlanRule(**kwargs)
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def update_rule(self, rule: PlanRule, **kwargs) -> PlanRule:
        for k, v in kwargs.items():
            if v is not None:
                setattr(rule, k, v)
        await self.db.flush()
        return rule

    async def delete_rule(self, rule: PlanRule) -> None:
        await self.db.delete(rule)
        await self.db.flush()

    async def record_simulation(self, **kwargs) -> PlanSimulation:
        sim = PlanSimulation(**kwargs)
        self.db.add(sim)
        await self.db.flush()
        return sim

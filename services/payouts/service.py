"""Payouts service — business logic (C-04).

Flujo:
1. compute_run(plan_id, period, department?, overrides?)
   → para cada empleado, arma su contexto (defaults + overrides),
     llama al motor JSONLogic (mismo de services/plans), guarda Payout con trace.
2. update_run_status(run_id, "approved" | "paid" | ...)
   → state machine. "paid" marca paid_at en cada Payout y emite notifs.
"""

import logging
from datetime import date

import httpx
from sqlalchemy import text

from shared.config import get_settings
from shared.notifications import emit_notification
from services.payouts.models import PayoutRun
from services.payouts.repository import PayoutsRepository
from services.payouts.schemas import (
    PayoutOut, RunDetail, RunIn, RunStatusUpdate, RunSummary,
)

# Reusamos el motor del servicio plans para que no haya doble verdad de cómo se evalúan reglas.
from services.plans.jsonlogic import JsonLogicError, evaluate

logger = logging.getLogger(__name__)


ALLOWED_TRANSITIONS = {
    "draft": {"pending_approval", "cancelled"},
    "pending_approval": {"approved", "draft", "cancelled"},
    "approved": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


def _default_context(emp: dict) -> dict:
    """Contexto demo cuando no se pasa override: deriva ventas/target del salario."""
    salary = float(emp.get("salary") or 0)
    return {
        "salary": salary,
        # En producción esto vendría de los KPIs del empleado o del CRM.
        "sales": salary * 0.08,
        "target": salary * 0.10,
        "deals_closed": 3,
    }


class PayoutsService:
    def __init__(self, repo: PayoutsRepository):
        self.repo = repo

    async def list_runs(self, tenant_id: int, status: str | None = None) -> list[RunSummary]:
        items = await self.repo.list_runs(tenant_id, status)
        return [RunSummary.model_validate(r) for r in items]

    async def get_run_detail(self, tenant_id: int, run_id: int) -> RunDetail | None:
        run = await self.repo.get_run(tenant_id, run_id)
        if not run:
            return None
        payouts = await self.repo.list_payouts_for_run(run_id)
        base = RunSummary.model_validate(run).model_dump()
        base["payouts"] = [PayoutOut.model_validate(p) for p in payouts]
        return RunDetail(**base)

    async def compute_run(
        self, tenant_id: int, user_id: int | None, payload: RunIn
    ) -> RunDetail:
        # 1) Pedir plan al servicio plans (HTTP interno)
        settings = get_settings()
        plan = await self._fetch_plan(settings.PLANS_SERVICE_URL, tenant_id, payload.plan_id)
        if not plan:
            raise ValueError(f"Plan {payload.plan_id} no existe o no accesible")

        # 2) Listar empleados del filtro
        employees = await self.repo.list_employees(
            tenant_id, department=payload.department_filter
        )
        if not employees:
            raise ValueError("No hay empleados activos para esta corrida")

        # 3) Crear el run
        run = await self.repo.create_run(
            tenant_id=tenant_id,
            plan_id=payload.plan_id,
            plan_name=plan["name"],
            period_label=payload.period_label,
            period_start=payload.period_start,
            period_end=payload.period_end,
            department_filter=payload.department_filter,
            currency=plan.get("currency") or "EUR",
            status="draft",
            total_amount=0,
            employee_count=0,
            notes=payload.notes,
            created_by=user_id,
        )

        # 4) Evaluar plan para cada empleado
        total = 0.0
        for emp in employees:
            ctx = {**_default_context(emp), **(plan.get("defaults") or {})}
            override = payload.context_overrides.get(emp["id"]) or {}
            ctx.update(override)

            traces: list[dict] = []
            amount = 0.0
            matched = 0

            for rule in plan.get("rules", []):
                try:
                    cond = evaluate(rule["when"], ctx)
                except JsonLogicError as e:
                    traces.append({"rule_id": rule.get("id"), "label": rule.get("label"),
                                   "matched": False, "error": f"when: {e}"})
                    continue
                if not bool(cond):
                    traces.append({"rule_id": rule.get("id"), "label": rule.get("label"),
                                   "matched": False})
                    continue
                try:
                    rule_amount = float(evaluate(rule["amount"], ctx))
                except (JsonLogicError, TypeError, ValueError) as e:
                    traces.append({"rule_id": rule.get("id"), "label": rule.get("label"),
                                   "matched": True, "error": f"amount: {e}"})
                    continue
                matched += 1
                amount += rule_amount
                traces.append({"rule_id": rule.get("id"), "label": rule.get("label"),
                               "matched": True, "amount": rule_amount})
                if plan.get("strategy") == "first-match":
                    break

            await self.repo.create_payout(
                tenant_id=tenant_id, run_id=run.id, employee_id=emp["id"],
                employee_name=emp["name"], department=emp.get("department"),
                context=ctx, amount=round(amount, 2), matched_rules=matched,
                trace=traces,
            )
            total += amount

        await self.repo.update_run(
            run, total_amount=round(total, 2), employee_count=len(employees),
        )
        return await self.get_run_detail(tenant_id, run.id) or RunDetail(
            **RunSummary.model_validate(run).model_dump(), payouts=[]
        )

    async def update_status(
        self, tenant_id: int, user_id: int | None, run_id: int, payload: RunStatusUpdate
    ) -> RunDetail:
        run = await self.repo.get_run(tenant_id, run_id)
        if not run:
            raise ValueError("Run no encontrado")
        if payload.status not in ALLOWED_TRANSITIONS.get(run.status, set()):
            raise ValueError(
                f"Transición ilegal {run.status} → {payload.status}. "
                f"Permitidas: {sorted(ALLOWED_TRANSITIONS.get(run.status, set())) or ['(ninguna)']}"
            )
        await self.repo.update_run(run, status=payload.status)

        # Si pasa a paid, marcar paid_at en cada payout + notificar
        if payload.status == "paid":
            payouts = await self.repo.list_payouts_for_run(run_id)
            today = date.today()
            for p in payouts:
                await self.repo.update_payout(p, paid_at=today)
                # Notif al empleado
                await self._notify_paid(tenant_id, p)

        detail = await self.get_run_detail(tenant_id, run_id)
        if not detail:
            raise RuntimeError("Run desapareció")
        return detail

    async def delete_run(self, tenant_id: int, run_id: int) -> bool:
        run = await self.repo.get_run(tenant_id, run_id)
        if not run:
            return False
        if run.status == "paid":
            raise ValueError("No se puede eliminar un run pagado")
        await self.repo.delete_run(run)
        return True

    # ─── helpers ───────────────────────────────────────
    async def _fetch_plan(self, plans_url: str, tenant_id: int, plan_id: int) -> dict | None:
        """Trae el plan vía endpoint interno del servicio plans (sin auth, en red Docker)."""
        # No tenemos un /internal/get-plan, usamos el endpoint GET protegido pero con un fetch directo a DB.
        # Para mantenerlo simple, leemos los datos directo de la DB:
        from sqlalchemy import text as sql
        row = (await self.repo.db.execute(
            sql("SELECT name, currency, strategy, defaults FROM svc_plans.commission_plans WHERE id=:id AND tenant_id=:tid"),
            {"id": plan_id, "tid": tenant_id},
        )).first()
        if not row:
            return None
        rules_rows = (await self.repo.db.execute(
            sql("SELECT id, label, priority, \"when\", amount FROM svc_plans.plan_rules WHERE plan_id=:id ORDER BY priority ASC"),
            {"id": plan_id},
        )).all()
        return {
            "name": row[0],
            "currency": row[1],
            "strategy": row[2],
            "defaults": row[3] or {},
            "rules": [
                {"id": r[0], "label": r[1], "priority": r[2], "when": r[3], "amount": r[4]}
                for r in rules_rows
            ],
        }

    async def _notify_paid(self, tenant_id: int, payout) -> None:
        # Encontrar el user_id del empleado
        row = (await self.repo.db.execute(
            text("SELECT user_id FROM svc_employees.employees WHERE id=:id AND tenant_id=:tid LIMIT 1"),
            {"id": payout.employee_id, "tid": tenant_id},
        )).first()
        if not row or not row[0]:
            return
        try:
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id, user_id=int(row[0]),
                title=f"Pago acreditado: {float(payout.amount):.2f}",
                body=f"Tu comisión del período fue marcada como pagada.",
                kind="success", category="payouts",
                action_url="/pagos",
                meta={"payout_id": payout.id, "amount": float(payout.amount)},
                email=True,  # P-04.2
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("payout_paid_notif_failed", exc_info=e)

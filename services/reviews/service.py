"""Reviews 360° service.

Reglas de asignación automática
-------------------------------
Para cada empleado activo creamos:
- 1 self review (el propio empleado se evalúa)
- 1 manager review (si tiene manager_id)
- N peer reviews (compañeros del mismo departamento, máx 3, aleatorios)
- M report reviews (si es manager de alguien, máx 3 reports aleatorios)

Cierre del ciclo
----------------
Calcula promedio:
- overall = media de todos los scores
- by_category = media por (performance|collaboration|growth|leadership)
- by_role = media por (self|manager|peer|report)
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from services.reviews.models import (
    ReviewAssignment, ReviewCycle, ReviewResponse, ReviewSummary,
)
from services.reviews.questions import QUESTIONS, questions_for_role


class ReviewsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Cycles ──────────────────────────────────────────────
    async def create_cycle(self, tenant_id: int, name: str, period: str, deadline, user_id: int | None) -> ReviewCycle:
        c = ReviewCycle(
            tenant_id=tenant_id, name=name, period=period,
            deadline=deadline, status="open", created_by=user_id,
        )
        self.db.add(c)
        await self.db.flush()
        return c

    async def list_cycles(self, tenant_id: int) -> list[dict]:
        cycles = (await self.db.execute(
            select(ReviewCycle).where(ReviewCycle.tenant_id == tenant_id).order_by(ReviewCycle.id.desc())
        )).scalars().all()

        out: list[dict] = []
        for c in cycles:
            total = (await self.db.execute(
                select(func.count(ReviewAssignment.id)).where(
                    ReviewAssignment.tenant_id == tenant_id,
                    ReviewAssignment.cycle_id == c.id,
                )
            )).scalar() or 0
            submitted = (await self.db.execute(
                select(func.count(ReviewAssignment.id)).where(
                    ReviewAssignment.tenant_id == tenant_id,
                    ReviewAssignment.cycle_id == c.id,
                    ReviewAssignment.status == "submitted",
                )
            )).scalar() or 0
            out.append({
                "id": c.id, "name": c.name, "period": c.period, "status": c.status,
                "deadline": c.deadline, "created_at": c.created_at, "closed_at": c.closed_at,
                "assignments_count": total, "submitted_count": submitted,
            })
        return out

    # ─── Auto-asignación ─────────────────────────────────────
    async def auto_assign(self, tenant_id: int, cycle_id: int) -> int:
        """Genera asignaciones para todos los empleados activos del tenant.

        Devuelve la cantidad de asignaciones creadas.
        """
        cycle = await self.db.get(ReviewCycle, cycle_id)
        if not cycle or cycle.tenant_id != tenant_id:
            raise ValueError("Ciclo no encontrado")
        if cycle.status == "closed":
            raise ValueError("No se puede reasignar un ciclo cerrado")

        # Limpiar asignaciones anteriores del ciclo (reasignación idempotente)
        await self.db.execute(text(
            "DELETE FROM svc_reviews.review_assignments WHERE cycle_id = :c AND tenant_id = :t"
        ), {"c": cycle_id, "t": tenant_id})

        # Cargar empleados activos
        emp_rows = (await self.db.execute(text(
            "SELECT id, manager_id, department FROM svc_employees.employees "
            "WHERE tenant_id = :t AND COALESCE(contract_status, 'active') = 'active'"
        ), {"t": tenant_id})).all()

        by_dept: dict[str, list[int]] = defaultdict(list)
        manager_of: dict[int, list[int]] = defaultdict(list)
        emp_info: dict[int, tuple[int | None, str | None]] = {}
        for eid, mid, dept in emp_rows:
            emp_info[eid] = (mid, dept)
            by_dept[dept or "_"].append(eid)
            if mid:
                manager_of[mid].append(eid)

        random.seed(cycle_id)  # determinístico por ciclo
        created = 0

        def add(reviewer_id: int, target_id: int, role: str):
            nonlocal created
            self.db.add(ReviewAssignment(
                tenant_id=tenant_id, cycle_id=cycle_id,
                reviewer_employee_id=reviewer_id, target_employee_id=target_id,
                role=role, status="pending",
            ))
            created += 1

        for target_id, (mid, dept) in emp_info.items():
            # self
            add(target_id, target_id, "self")
            # manager
            if mid:
                add(mid, target_id, "manager")
            # peers — del mismo dept, máx 3
            same_dept = [e for e in by_dept[dept or "_"] if e != target_id and e != mid]
            peers = random.sample(same_dept, min(3, len(same_dept)))
            for p in peers:
                add(p, target_id, "peer")
            # reports — si target es manager de alguien, máx 3
            reports = manager_of.get(target_id, [])
            for r in random.sample(reports, min(3, len(reports))):
                add(r, target_id, "report")

        await self.db.flush()
        return created

    # ─── Reviewer view ───────────────────────────────────────
    async def list_pending(self, tenant_id: int, employee_id: int) -> list[dict]:
        rows = (await self.db.execute(text(
            "SELECT a.id, a.cycle_id, c.name, c.period, "
            "  a.target_employee_id, e.first_name, e.last_name, a.role, a.status "
            "FROM svc_reviews.review_assignments a "
            "JOIN svc_reviews.review_cycles c ON c.id = a.cycle_id "
            "LEFT JOIN svc_employees.employees e ON e.id = a.target_employee_id "
            "WHERE a.tenant_id = :t AND a.reviewer_employee_id = :rid AND a.status = 'pending' "
            "AND c.status != 'closed' "
            "ORDER BY c.deadline NULLS LAST, c.id DESC"
        ), {"t": tenant_id, "rid": employee_id})).all()
        return [{
            "id": r[0], "cycle_id": r[1], "cycle_name": r[2], "cycle_period": r[3],
            "target_employee_id": r[4], "target_name": f"{r[5] or ''} {r[6] or ''}".strip() or f"Empleado #{r[4]}",
            "role": r[7], "status": r[8],
        } for r in rows]

    async def get_form(self, tenant_id: int, assignment_id: int, reviewer_id: int) -> dict:
        a = await self.db.get(ReviewAssignment, assignment_id)
        if not a or a.tenant_id != tenant_id or a.reviewer_employee_id != reviewer_id:
            raise ValueError("Asignación no encontrada")
        target = (await self.db.execute(text(
            "SELECT first_name, last_name, position FROM svc_employees.employees WHERE id = :id AND tenant_id = :t"
        ), {"id": a.target_employee_id, "t": tenant_id})).first()
        return {
            "assignment_id": a.id, "cycle_id": a.cycle_id,
            "role": a.role, "status": a.status,
            "target_employee_id": a.target_employee_id,
            "target_name": f"{target[0]} {target[1]}" if target else "—",
            "target_position": target[2] if target else None,
            "questions": [{"code": q.code, "category": q.category, "text": q.text}
                          for q in questions_for_role(a.role)],
        }

    async def submit(self, tenant_id: int, assignment_id: int, reviewer_id: int, responses: list[dict]) -> dict:
        a = await self.db.get(ReviewAssignment, assignment_id)
        if not a or a.tenant_id != tenant_id or a.reviewer_employee_id != reviewer_id:
            raise ValueError("Asignación no encontrada")
        if a.status == "submitted":
            raise ValueError("Ya fue enviada")

        allowed = {q.code: q.category for q in questions_for_role(a.role)}
        for r in responses:
            if r["question_code"] not in allowed:
                raise ValueError(f"Pregunta inválida para rol {a.role}: {r['question_code']}")
            self.db.add(ReviewResponse(
                tenant_id=tenant_id, assignment_id=a.id,
                question_code=r["question_code"], category=allowed[r["question_code"]],
                score=r["score"], comment=(r.get("comment") or None),
            ))

        a.status = "submitted"
        a.submitted_at = datetime.now(timezone.utc)

        # Si el ciclo estaba en 'open', moverlo a 'in_progress'
        cycle = await self.db.get(ReviewCycle, a.cycle_id)
        if cycle and cycle.status == "open":
            cycle.status = "in_progress"

        await self.db.flush()
        return {"assignment_id": a.id, "status": a.status, "responses": len(responses)}

    # ─── Close cycle + aggregation ───────────────────────────
    async def close_cycle(self, tenant_id: int, cycle_id: int) -> dict:
        cycle = await self.db.get(ReviewCycle, cycle_id)
        if not cycle or cycle.tenant_id != tenant_id:
            raise ValueError("Ciclo no encontrado")
        if cycle.status == "closed":
            raise ValueError("Ya está cerrado")

        # Borrar summaries previos (si reabrimos en el futuro, recalcula limpio)
        await self.db.execute(text(
            "DELETE FROM svc_reviews.review_summaries WHERE cycle_id = :c AND tenant_id = :t"
        ), {"c": cycle_id, "t": tenant_id})

        rows = (await self.db.execute(text(
            "SELECT a.target_employee_id, a.role, r.category, r.score "
            "FROM svc_reviews.review_assignments a "
            "JOIN svc_reviews.review_responses r ON r.assignment_id = a.id "
            "WHERE a.cycle_id = :c AND a.tenant_id = :t"
        ), {"c": cycle_id, "t": tenant_id})).all()

        # Buckets per target
        per_target: dict[int, dict[str, list[int]]] = defaultdict(lambda: {
            "all": [], "by_cat": defaultdict(list), "by_role": defaultdict(list),
        })
        for target_id, role, cat, score in rows:
            per_target[target_id]["all"].append(score)
            per_target[target_id]["by_cat"][cat].append(score)
            per_target[target_id]["by_role"][role].append(score)

        for target_id, b in per_target.items():
            self.db.add(ReviewSummary(
                tenant_id=tenant_id, cycle_id=cycle_id, employee_id=target_id,
                overall_score=round(sum(b["all"]) / len(b["all"]), 2) if b["all"] else 0.0,
                by_category={k: round(sum(v) / len(v), 2) for k, v in b["by_cat"].items()},
                by_role={k: round(sum(v) / len(v), 2) for k, v in b["by_role"].items()},
                responses_count=len(b["all"]),
            ))

        cycle.status = "closed"
        cycle.closed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"cycle_id": cycle.id, "summaries": len(per_target)}

    async def get_employee_summary(self, tenant_id: int, employee_id: int) -> list[dict]:
        rows = (await self.db.execute(text(
            "SELECT s.*, c.name AS cycle_name, c.period AS cycle_period, "
            "  e.first_name, e.last_name "
            "FROM svc_reviews.review_summaries s "
            "JOIN svc_reviews.review_cycles c ON c.id = s.cycle_id "
            "LEFT JOIN svc_employees.employees e ON e.id = s.employee_id "
            "WHERE s.tenant_id = :t AND s.employee_id = :eid "
            "ORDER BY c.id DESC"
        ), {"t": tenant_id, "eid": employee_id})).mappings().all()
        return [{
            "cycle_id": r["cycle_id"], "cycle_name": r["cycle_name"], "cycle_period": r["cycle_period"],
            "employee_id": r["employee_id"],
            "employee_name": f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "—",
            "overall_score": float(r["overall_score"]),
            "by_category": r["by_category"], "by_role": r["by_role"],
            "responses_count": r["responses_count"],
        } for r in rows]

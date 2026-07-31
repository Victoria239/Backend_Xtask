"""Onboarding service - DB repository."""

from datetime import date, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.onboarding.models import (
    OnboardingAssignment,
    OnboardingAssignmentStep,
    OnboardingTemplate,
    OnboardingTemplateStep,
)


class OnboardingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Templates ────────────────────────────────────────────────
    async def list_templates(self, tenant_id: int) -> list[OnboardingTemplate]:
        stmt = (
            select(OnboardingTemplate)
            .where(OnboardingTemplate.tenant_id == tenant_id)
            .options(selectinload(OnboardingTemplate.steps))
            .order_by(OnboardingTemplate.is_default.desc(), OnboardingTemplate.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_template(self, tenant_id: int, template_id: int) -> OnboardingTemplate | None:
        stmt = (
            select(OnboardingTemplate)
            .where(OnboardingTemplate.tenant_id == tenant_id, OnboardingTemplate.id == template_id)
            .options(selectinload(OnboardingTemplate.steps))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_default_template(self, tenant_id: int) -> OnboardingTemplate | None:
        stmt = (
            select(OnboardingTemplate)
            .where(OnboardingTemplate.tenant_id == tenant_id, OnboardingTemplate.is_default.is_(True))
            .options(selectinload(OnboardingTemplate.steps))
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_template(
        self, tenant_id: int, name: str, description: str | None, is_default: bool, steps: list[dict],
    ) -> OnboardingTemplate:
        if is_default:
            # Unset previous default
            await self.db.execute(
                update(OnboardingTemplate)
                .where(OnboardingTemplate.tenant_id == tenant_id, OnboardingTemplate.is_default.is_(True))
                .values(is_default=False)
            )
        tpl = OnboardingTemplate(tenant_id=tenant_id, name=name, description=description, is_default=is_default)
        self.db.add(tpl)
        await self.db.flush()
        for s in steps:
            self.db.add(OnboardingTemplateStep(
                template_id=tpl.id,
                position=s.get("position", 0),
                title=s["title"],
                description=s.get("description"),
                category=s.get("category", "general"),
                due_days=s.get("due_days", 7),
                required=s.get("required", True),
            ))
        await self.db.flush()
        await self.db.refresh(tpl, attribute_names=["steps"])
        return tpl

    async def delete_template(self, tenant_id: int, template_id: int) -> bool:
        tpl = await self.get_template(tenant_id, template_id)
        if not tpl:
            return False
        await self.db.delete(tpl)
        return True

    # ─── Assignments ──────────────────────────────────────────────
    async def get_assignment_for_employee(
        self, tenant_id: int, employee_id: int,
    ) -> OnboardingAssignment | None:
        stmt = (
            select(OnboardingAssignment)
            .where(
                OnboardingAssignment.tenant_id == tenant_id,
                OnboardingAssignment.employee_id == employee_id,
            )
            .options(selectinload(OnboardingAssignment.steps))
            .order_by(OnboardingAssignment.started_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_assignment(self, tenant_id: int, assignment_id: int) -> OnboardingAssignment | None:
        stmt = (
            select(OnboardingAssignment)
            .where(OnboardingAssignment.tenant_id == tenant_id, OnboardingAssignment.id == assignment_id)
            .options(selectinload(OnboardingAssignment.steps))
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_assignment_from_template(
        self, tenant_id: int, employee_id: int, template: OnboardingTemplate,
    ) -> OnboardingAssignment:
        asg = OnboardingAssignment(
            tenant_id=tenant_id, employee_id=employee_id, template_id=template.id,
        )
        self.db.add(asg)
        await self.db.flush()
        today = date.today()
        for s in template.steps:
            self.db.add(OnboardingAssignmentStep(
                tenant_id=tenant_id,
                assignment_id=asg.id,
                position=s.position,
                title=s.title,
                description=s.description,
                category=s.category,
                required=s.required,
                due_date=today + timedelta(days=s.due_days),
                status="pending",
            ))
        await self.db.flush()
        await self.db.refresh(asg, attribute_names=["steps"])
        return asg

    async def update_step_status(
        self, tenant_id: int, step_id: int, status: str, completed_by: int | None,
    ) -> OnboardingAssignmentStep | None:
        stmt = (
            update(OnboardingAssignmentStep)
            .where(
                OnboardingAssignmentStep.id == step_id,
                OnboardingAssignmentStep.tenant_id == tenant_id,
            )
            .values(
                status=status,
                completed_at=datetime.utcnow() if status in ("done", "skipped") else None,
                completed_by=completed_by if status in ("done", "skipped") else None,
            )
            .returning(OnboardingAssignmentStep)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def mark_assignment_complete_if_done(self, assignment_id: int) -> bool:
        """Si todos los pasos required están done/skipped, marca completed_at."""
        result = await self.db.execute(text("""
            UPDATE svc_onboarding.assignments
            SET completed_at = NOW()
            WHERE id = :aid
              AND completed_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM svc_onboarding.assignment_steps s
                  WHERE s.assignment_id = :aid
                    AND s.required = true
                    AND s.status NOT IN ('done', 'skipped')
              )
            RETURNING id
        """), {"aid": assignment_id})
        return result.first() is not None

    async def list_assignments_summary(self, tenant_id: int) -> list[dict]:
        result = await self.db.execute(text("""
            SELECT
              a.id AS assignment_id,
              a.employee_id,
              COALESCE(e.first_name || ' ' || e.last_name, 'Empleado #' || a.employee_id) AS employee_name,
              COUNT(s.id) AS total_steps,
              COUNT(s.id) FILTER (WHERE s.status IN ('done', 'skipped')) AS done_steps,
              a.started_at,
              a.completed_at
            FROM svc_onboarding.assignments a
            LEFT JOIN svc_onboarding.assignment_steps s ON s.assignment_id = a.id
            LEFT JOIN svc_employees.employees e ON e.id = a.employee_id
            WHERE a.tenant_id = :tid
            GROUP BY a.id, e.first_name, e.last_name, a.employee_id, a.started_at, a.completed_at
            ORDER BY a.completed_at NULLS FIRST, a.started_at DESC
        """), {"tid": tenant_id})
        rows = result.mappings().all()
        return [dict(r) for r in rows]

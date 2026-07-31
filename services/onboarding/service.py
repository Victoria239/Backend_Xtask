"""Onboarding service - business logic (H-02)."""

from shared.exceptions import NotFoundException
from shared.notifications import emit_notification
from services.onboarding.models import OnboardingAssignment
from services.onboarding.repository import OnboardingRepository
from services.onboarding.schemas import TemplateIn


class OnboardingService:
    def __init__(self, repo: OnboardingRepository):
        self.repo = repo

    # ─── Templates ────────────────────────────────────────────
    async def list_templates(self, tenant_id: int):
        return await self.repo.list_templates(tenant_id)

    async def create_template(self, tenant_id: int, payload: TemplateIn):
        return await self.repo.create_template(
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            is_default=payload.is_default,
            steps=[s.model_dump() for s in payload.steps],
        )

    async def delete_template(self, tenant_id: int, template_id: int) -> None:
        ok = await self.repo.delete_template(tenant_id, template_id)
        if not ok:
            raise NotFoundException("Template", template_id)

    # ─── Assignments ──────────────────────────────────────────
    async def get_for_employee(self, tenant_id: int, employee_id: int) -> OnboardingAssignment | None:
        return await self.repo.get_assignment_for_employee(tenant_id, employee_id)

    async def assign(
        self, tenant_id: int, employee_id: int, template_id: int | None,
    ) -> OnboardingAssignment:
        if template_id:
            tpl = await self.repo.get_template(tenant_id, template_id)
        else:
            tpl = await self.repo.get_default_template(tenant_id)
        if not tpl:
            raise NotFoundException("Template", template_id or "default")
        return await self.repo.create_assignment_from_template(tenant_id, employee_id, tpl)

    async def update_step(
        self, tenant_id: int, step_id: int, status: str, completed_by: int | None,
    ):
        step = await self.repo.update_step_status(tenant_id, step_id, status, completed_by)
        if not step:
            raise NotFoundException("Step", step_id)

        # Si el paso se completó, chequea si el assignment está done
        if status in ("done", "skipped"):
            became_complete = await self.repo.mark_assignment_complete_if_done(step.assignment_id)
            if became_complete:
                # Notif al user
                await emit_notification(
                    self.repo.db,
                    tenant_id=tenant_id,
                    user_id=completed_by,
                    title="Onboarding completo",
                    body="Terminaste todos los pasos requeridos de tu onboarding. ¡Bienvenido al equipo!",
                    kind="success",
                    category="onboarding",
                    action_url="/onboarding",
                    meta={"assignment_id": step.assignment_id},
                )
        return step

    async def admin_summary(self, tenant_id: int):
        return await self.repo.list_assignments_summary(tenant_id)

"""Approvals service — engine genérico (C-05)."""

import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.notifications import emit_notification
from services.approvals.models import (
    ApprovalFlow, ApprovalInstance, FlowStep, InstanceStep,
)
from services.approvals.schemas import (
    FlowDetail, FlowIn, FlowOut, InstanceDetail, InstanceStepOut, InstanceSummary,
    StartInstance, StepDecision, StepOut,
)

logger = logging.getLogger(__name__)


class ApprovalsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Flows CRUD ─────────────────────────────────────────
    async def list_flows(self, tenant_id: int, target_kind: str | None = None) -> list[FlowOut]:
        stmt = select(ApprovalFlow).where(ApprovalFlow.tenant_id == tenant_id)
        if target_kind:
            stmt = stmt.where(ApprovalFlow.target_kind == target_kind)
        stmt = stmt.order_by(ApprovalFlow.priority.desc(), ApprovalFlow.created_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [FlowOut.model_validate(f) for f in rows]

    async def get_flow_detail(self, tenant_id: int, flow_id: int) -> FlowDetail | None:
        stmt = select(ApprovalFlow).where(
            ApprovalFlow.tenant_id == tenant_id, ApprovalFlow.id == flow_id
        )
        flow = (await self.db.execute(stmt)).scalar_one_or_none()
        if not flow:
            return None
        steps = (await self.db.execute(
            select(FlowStep).where(FlowStep.flow_id == flow_id).order_by(FlowStep.position.asc())
        )).scalars().all()
        base = FlowOut.model_validate(flow).model_dump()
        base["steps"] = [StepOut.model_validate(s) for s in steps]
        return FlowDetail(**base)

    async def create_flow(self, tenant_id: int, payload: FlowIn) -> FlowDetail:
        flow = ApprovalFlow(
            tenant_id=tenant_id,
            name=payload.name, description=payload.description,
            target_kind=payload.target_kind, priority=payload.priority,
            active=payload.active, filter_jsonlogic=payload.filter_jsonlogic,
        )
        self.db.add(flow)
        await self.db.flush()
        for s in payload.steps:
            self.db.add(FlowStep(
                tenant_id=tenant_id, flow_id=flow.id, position=s.position,
                name=s.name, approver_role=s.approver_role,
                approver_user_id=s.approver_user_id,
                auto_approve_below=s.auto_approve_below, sla_hours=s.sla_hours,
            ))
        await self.db.flush()
        detail = await self.get_flow_detail(tenant_id, flow.id)
        if detail is None:
            raise RuntimeError("Flow desapareció")
        return detail

    # ─── Instancias ─────────────────────────────────────────
    async def list_instances(
        self, tenant_id: int, *, status: str | None = None,
        approver_user_id: int | None = None,
    ) -> list[InstanceSummary]:
        """Lista instancias. Si approver_user_id, devuelve solo las que ESE user debe aprobar ahora."""
        stmt = select(ApprovalInstance).where(ApprovalInstance.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(ApprovalInstance.status == status)
        if approver_user_id:
            # Pending instances where the current step's approver_user_id matches
            # Subquery: current step
            subq = (
                select(InstanceStep.instance_id)
                .where(
                    InstanceStep.tenant_id == tenant_id,
                    InstanceStep.approver_user_id == approver_user_id,
                    InstanceStep.status == "pending",
                )
            )
            stmt = stmt.where(ApprovalInstance.id.in_(subq))
        stmt = stmt.order_by(ApprovalInstance.created_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [InstanceSummary.model_validate(i) for i in rows]

    async def get_instance_detail(
        self, tenant_id: int, instance_id: int
    ) -> InstanceDetail | None:
        inst = (await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.tenant_id == tenant_id, ApprovalInstance.id == instance_id,
            )
        )).scalar_one_or_none()
        if not inst:
            return None
        steps = (await self.db.execute(
            select(InstanceStep).where(InstanceStep.instance_id == instance_id).order_by(InstanceStep.position.asc())
        )).scalars().all()
        base = InstanceSummary.model_validate(inst).model_dump()
        base["steps"] = [InstanceStepOut.model_validate(s) for s in steps]
        return InstanceDetail(**base)

    async def start_instance(self, tenant_id: int, payload: StartInstance) -> InstanceDetail:
        # 1) Encontrar el flow activo de mayor prioridad para este target_kind
        flow = (await self.db.execute(
            select(ApprovalFlow).where(
                ApprovalFlow.tenant_id == tenant_id,
                ApprovalFlow.target_kind == payload.target_kind,
                ApprovalFlow.active.is_(True),
            ).order_by(ApprovalFlow.priority.desc()).limit(1)
        )).scalar_one_or_none()
        if not flow:
            raise ValueError(f"No hay flow activo para {payload.target_kind}")

        # 2) Crear la instance
        inst = ApprovalInstance(
            tenant_id=tenant_id, flow_id=flow.id,
            target_kind=payload.target_kind, target_id=payload.target_id,
            status="pending", current_step_position=1,
            requester_user_id=payload.requester_user_id, summary=payload.summary,
            target_employee_id=payload.target_employee_id,
        )
        self.db.add(inst)
        await self.db.flush()

        # 3) Resolver y crear cada step
        flow_steps = (await self.db.execute(
            select(FlowStep).where(FlowStep.flow_id == flow.id).order_by(FlowStep.position.asc())
        )).scalars().all()

        for fs in flow_steps:
            approver = await self._resolve_approver(
                tenant_id, fs, payload.target_employee_id, payload.context,
            )
            self.db.add(InstanceStep(
                tenant_id=tenant_id, instance_id=inst.id,
                position=fs.position, name=fs.name,
                approver_user_id=approver, status="pending",
            ))
        await self.db.flush()

        # 4) Notif al primer aprobador
        first_step = (await self.db.execute(
            select(InstanceStep)
            .where(InstanceStep.instance_id == inst.id, InstanceStep.position == 1)
        )).scalar_one_or_none()
        if first_step and first_step.approver_user_id:
            await self._notify_pending(tenant_id, inst, first_step)

        detail = await self.get_instance_detail(tenant_id, inst.id)
        if detail is None:
            raise RuntimeError("Instance desapareció")
        return detail

    async def decide(
        self, tenant_id: int, user_id: int, instance_id: int, payload: StepDecision
    ) -> InstanceDetail:
        inst = (await self.db.execute(
            select(ApprovalInstance).where(
                ApprovalInstance.tenant_id == tenant_id, ApprovalInstance.id == instance_id,
            )
        )).scalar_one_or_none()
        if not inst:
            raise ValueError("Instance no encontrada")
        if inst.status != "pending":
            raise ValueError(f"La instance ya no acepta decisiones (estado {inst.status})")

        # Encontrar el step actual
        current_step = (await self.db.execute(
            select(InstanceStep).where(
                InstanceStep.instance_id == instance_id,
                InstanceStep.position == inst.current_step_position,
            )
        )).scalar_one_or_none()
        if not current_step:
            raise ValueError("No hay step actual")
        if current_step.approver_user_id and current_step.approver_user_id != user_id:
            raise ValueError("No sos el aprobador de este paso")

        # Marcar decisión
        current_step.status = payload.decision
        current_step.decided_at = datetime.utcnow()
        current_step.decided_by = user_id
        current_step.note = payload.note
        await self.db.flush()

        if payload.decision == "rejected":
            inst.status = "rejected"
            inst.finished_at = datetime.utcnow()
            await self.db.flush()
            await self._notify_requester(tenant_id, inst, "rejected")
        else:
            # Approved → ¿hay siguiente step?
            next_pos = inst.current_step_position + 1
            next_step = (await self.db.execute(
                select(InstanceStep).where(
                    InstanceStep.instance_id == instance_id,
                    InstanceStep.position == next_pos,
                )
            )).scalar_one_or_none()
            if next_step:
                inst.current_step_position = next_pos
                await self.db.flush()
                if next_step.approver_user_id:
                    await self._notify_pending(tenant_id, inst, next_step)
            else:
                # Fin del flow → instance approved
                inst.status = "approved"
                inst.finished_at = datetime.utcnow()
                await self.db.flush()
                await self._notify_requester(tenant_id, inst, "approved")

        detail = await self.get_instance_detail(tenant_id, instance_id)
        if detail is None:
            raise RuntimeError("Instance desapareció")
        return detail

    # ─── helpers ───────────────────────────────────────
    async def _resolve_approver(
        self, tenant_id: int, fs: FlowStep, target_emp_id: int | None, context: dict,
    ) -> int | None:
        """Devuelve el user_id que debe aprobar este paso."""
        if fs.approver_role == "specific_user":
            return fs.approver_user_id
        if fs.approver_role == "admin":
            # Primer admin del tenant
            row = (await self.db.execute(
                text("SELECT id FROM svc_auth.users WHERE role='admin' LIMIT 1"),
            )).first()
            return int(row[0]) if row and row[0] else None
        if fs.approver_role == "manager_of_employee" and target_emp_id:
            row = (await self.db.execute(
                text(
                    "SELECT m.user_id FROM svc_employees.employees e "
                    "LEFT JOIN svc_employees.employees m ON m.id = e.manager_id "
                    "WHERE e.id = :eid AND e.tenant_id = :tid LIMIT 1"
                ),
                {"eid": target_emp_id, "tid": tenant_id},
            )).first()
            return int(row[0]) if row and row[0] else None
        if fs.approver_role == "department_head" and target_emp_id:
            # Empleado más senior del mismo departamento (heurística)
            row = (await self.db.execute(
                text(
                    "SELECT user_id FROM svc_employees.employees "
                    "WHERE tenant_id = :tid "
                    "AND department = (SELECT department FROM svc_employees.employees WHERE id = :eid AND tenant_id = :tid) "
                    "AND user_id IS NOT NULL "
                    "ORDER BY salary DESC NULLS LAST LIMIT 1"
                ),
                {"eid": target_emp_id, "tid": tenant_id},
            )).first()
            return int(row[0]) if row and row[0] else None
        return None

    async def _notify_pending(self, tenant_id: int, inst: ApprovalInstance, step: InstanceStep) -> None:
        if not step.approver_user_id:
            return
        try:
            await emit_notification(
                self.db,
                tenant_id=tenant_id, user_id=step.approver_user_id,
                title=f"Aprobación pendiente: {step.name}",
                body=inst.summary or f"{inst.target_kind} #{inst.target_id}",
                kind="info", category="approvals",
                action_url=f"/aprobaciones/{inst.id}",
                meta={"instance_id": inst.id, "step": step.position},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("approvals_pending_notif_failed", exc_info=e)

    async def _notify_requester(self, tenant_id: int, inst: ApprovalInstance, status: str) -> None:
        if not inst.requester_user_id:
            return
        try:
            await emit_notification(
                self.db,
                tenant_id=tenant_id, user_id=inst.requester_user_id,
                title=f"Tu solicitud fue {'aprobada' if status == 'approved' else 'rechazada'}",
                body=inst.summary or f"{inst.target_kind} #{inst.target_id}",
                kind="success" if status == "approved" else "warning",
                category="approvals",
                action_url=f"/aprobaciones/{inst.id}",
                meta={"instance_id": inst.id, "final_status": status},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("approvals_finish_notif_failed", exc_info=e)

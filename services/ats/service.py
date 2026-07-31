"""ATS service — business logic (H-03)."""

import logging
from datetime import datetime

from shared.notifications import emit_notification
from services.ats.models import Application, Pipeline, Stage
from services.ats.repository import AtsRepository
from services.ats.schemas import (
    ApplicationEventOut, ApplicationIn, ApplicationOut, CandidateIn, CandidateOut,
    DEFAULT_STAGES, KanbanCard, KanbanColumn, KanbanView, MoveStage, PipelineDetail,
    PipelineIn, PipelineSummary, PipelineUpdate, StageOut,
)

logger = logging.getLogger(__name__)


class AtsService:
    def __init__(self, repo: AtsRepository):
        self.repo = repo

    # ─── Pipelines ────────────────────────────────────────
    async def list_pipelines(self, tenant_id: int, status: str | None = None) -> list[PipelineSummary]:
        rows = await self.repo.list_pipelines(tenant_id, status)
        return [PipelineSummary(**{**p.__dict__, "application_count": ac}) for p, ac in rows]

    async def get_pipeline_detail(self, tenant_id: int, pipeline_id: int) -> PipelineDetail | None:
        p = await self.repo.get_pipeline(tenant_id, pipeline_id)
        if not p:
            return None
        stages = await self.repo.list_stages(pipeline_id)
        apps = await self.repo.list_applications_for_pipeline(pipeline_id)
        base = PipelineSummary.model_validate(p).model_dump()
        base["application_count"] = len(apps)
        base["stages"] = [StageOut.model_validate(s) for s in stages]
        return PipelineDetail(**base)

    async def create_pipeline(self, tenant_id: int, payload: PipelineIn) -> PipelineDetail:
        data = payload.model_dump(exclude={"stages"})
        data["tenant_id"] = tenant_id
        pipeline = await self.repo.create_pipeline(**data)

        # Seed stages: si vino lista, usamos esa; sino los 5 default
        stages_payload = payload.stages or [
            {"name": s["name"], "position": s["position"], "color": s["color"],
             "is_terminal": s.get("is_terminal", False)}
            for s in DEFAULT_STAGES
        ]
        for s in stages_payload:
            await self.repo.create_stage(
                tenant_id=tenant_id, pipeline_id=pipeline.id,
                **(s if isinstance(s, dict) else s.model_dump()),
            )
        detail = await self.get_pipeline_detail(tenant_id, pipeline.id)
        if detail is None:
            raise RuntimeError("Pipeline desapareció tras crearlo")
        return detail

    async def update_pipeline(
        self, tenant_id: int, pipeline_id: int, payload: PipelineUpdate
    ) -> PipelineDetail | None:
        p = await self.repo.get_pipeline(tenant_id, pipeline_id)
        if not p:
            return None
        await self.repo.update_pipeline(p, **payload.model_dump(exclude_unset=True))
        return await self.get_pipeline_detail(tenant_id, pipeline_id)

    async def delete_pipeline(self, tenant_id: int, pipeline_id: int) -> bool:
        p = await self.repo.get_pipeline(tenant_id, pipeline_id)
        if not p:
            return False
        await self.repo.delete_pipeline(p)
        return True

    # ─── Candidates ────────────────────────────────────────
    async def list_candidates(
        self, tenant_id: int, search: str | None = None
    ) -> list[CandidateOut]:
        items = await self.repo.list_candidates(tenant_id, search)
        return [CandidateOut.model_validate(c) for c in items]

    async def create_candidate(self, tenant_id: int, payload: CandidateIn) -> CandidateOut:
        c = await self.repo.create_candidate(tenant_id=tenant_id, **payload.model_dump())
        return CandidateOut.model_validate(c)

    async def update_candidate(
        self, tenant_id: int, candidate_id: int, payload: CandidateIn
    ) -> CandidateOut | None:
        c = await self.repo.get_candidate(tenant_id, candidate_id)
        if not c:
            return None
        await self.repo.update_candidate(c, **payload.model_dump())
        return CandidateOut.model_validate(c)

    # ─── Applications ─────────────────────────────────────
    async def add_application(
        self, tenant_id: int, pipeline_id: int, user_id: int | None, payload: ApplicationIn
    ) -> ApplicationOut:
        p = await self.repo.get_pipeline(tenant_id, pipeline_id)
        if not p:
            raise ValueError("Pipeline no existe")
        c = await self.repo.get_candidate(tenant_id, payload.candidate_id)
        if not c:
            raise ValueError("Candidato no existe")

        stages = await self.repo.list_stages(pipeline_id)
        if not stages:
            raise ValueError("El pipeline no tiene stages")
        first_stage = stages[0]

        app = await self.repo.create_application(
            tenant_id=tenant_id, pipeline_id=pipeline_id, candidate_id=payload.candidate_id,
            stage_id=first_stage.id, expected_salary=payload.expected_salary,
        )
        await self.repo.add_event(
            tenant_id=tenant_id, application_id=app.id, kind="stage_change",
            from_stage_id=None, to_stage_id=first_stage.id,
            actor_user_id=user_id, note="Candidato agregado al pipeline",
        )
        return ApplicationOut.model_validate(app)

    async def move_application(
        self, tenant_id: int, app_id: int, user_id: int | None, payload: MoveStage
    ) -> ApplicationOut:
        app = await self.repo.get_application(tenant_id, app_id)
        if not app:
            raise ValueError("Application no existe")
        current_stage = await self.repo.get_stage(tenant_id, app.stage_id)
        if current_stage and current_stage.is_terminal:
            raise ValueError("Esta application está en un stage terminal — no se puede mover")

        target = await self.repo.get_stage(tenant_id, payload.to_stage_id)
        if not target or target.pipeline_id != app.pipeline_id:
            raise ValueError("Stage destino no pertenece a este pipeline")

        old_stage = app.stage_id
        await self.repo.update_application(app, stage_id=target.id)

        # Si el target es terminal "Hired" o "Rejected", marcar final_decision
        if target.is_terminal:
            decision_map = {"hired": "hired", "rejected": "rejected"}
            await self.repo.update_application(
                app, final_decision=decision_map.get(target.name.lower(), target.name.lower()),
            )

        await self.repo.add_event(
            tenant_id=tenant_id, application_id=app.id, kind="stage_change",
            from_stage_id=old_stage, to_stage_id=target.id,
            actor_user_id=user_id, note=payload.note,
        )

        # Notif al hiring manager si se mueve a Offer o un terminal
        if target.name in ("Offer", "Hired", "Rejected"):
            await self._notify_manager(tenant_id, app, target.name)

        return ApplicationOut.model_validate(app)

    async def _notify_manager(self, tenant_id: int, app: Application, stage_name: str) -> None:
        p = await self.repo.get_pipeline(tenant_id, app.pipeline_id)
        if not p or not p.hiring_manager_employee_id:
            return
        from sqlalchemy import text
        row = (await self.repo.db.execute(
            text("SELECT user_id FROM svc_employees.employees WHERE id = :eid AND tenant_id = :tid LIMIT 1"),
            {"eid": p.hiring_manager_employee_id, "tid": tenant_id},
        )).first()
        if not row or not row[0]:
            return
        candidate = await self.repo.get_candidate(tenant_id, app.candidate_id)
        c_name = f"{candidate.first_name} {candidate.last_name}" if candidate else "?"
        try:
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id, user_id=int(row[0]),
                title=f"{c_name} pasó a {stage_name}",
                body=f"Pipeline: {p.title}",
                kind="info", category="ats",
                action_url=f"/recruiting/{p.id}",
                meta={"pipeline_id": p.id, "application_id": app.id, "stage": stage_name},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ats_stage_notif_failed", exc_info=e)

    async def list_events(self, tenant_id: int, app_id: int) -> list[ApplicationEventOut]:
        app = await self.repo.get_application(tenant_id, app_id)
        if not app:
            raise ValueError("Application no encontrada")
        evs = await self.repo.list_events(app_id)
        return [ApplicationEventOut.model_validate(e) for e in evs]

    # ─── Kanban view ────────────────────────────────────────
    async def kanban(self, tenant_id: int, pipeline_id: int) -> KanbanView:
        p = await self.repo.get_pipeline(tenant_id, pipeline_id)
        if not p:
            raise ValueError("Pipeline no existe")
        stages = await self.repo.list_stages(pipeline_id)
        apps = await self.repo.list_applications_for_pipeline(pipeline_id)

        # Map de candidatos
        cand_ids = list({a.candidate_id for a in apps})
        candidates = []
        for cid in cand_ids:
            c = await self.repo.get_candidate(tenant_id, cid)
            if c:
                candidates.append(c)
        cmap = {c.id: c for c in candidates}

        # Días en stage (último stage_change)
        days_map = {}
        for a in apps:
            ev = await self.repo.latest_stage_change(a.id)
            if ev:
                delta = (datetime.utcnow() - ev.created_at.replace(tzinfo=None)).days
                days_map[a.id] = max(0, delta)
            else:
                days_map[a.id] = 0

        columns = []
        for st in stages:
            cards = []
            for a in apps:
                if a.stage_id != st.id:
                    continue
                c = cmap.get(a.candidate_id)
                cards.append(KanbanCard(
                    application_id=a.id, candidate_id=a.candidate_id,
                    candidate_name=f"{c.first_name} {c.last_name}" if c else "?",
                    candidate_email=c.email if c else None,
                    candidate_source=c.source if c else None,
                    stage_id=a.stage_id, days_in_stage=days_map[a.id],
                ))
            columns.append(KanbanColumn(stage=StageOut.model_validate(st), cards=cards))
        return KanbanView(pipeline_id=p.id, pipeline_title=p.title, columns=columns)

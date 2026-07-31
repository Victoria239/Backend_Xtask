"""ATS service — DB repository (H-03)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.ats.models import (
    Application, ApplicationEvent, Candidate, Pipeline, Stage,
)


class AtsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Pipelines ────────────────────────────────────────
    async def list_pipelines(
        self, tenant_id: int, status: str | None = None
    ) -> list[tuple[Pipeline, int]]:
        stmt = (
            select(Pipeline, func.count(Application.id).label("app_count"))
            .outerjoin(Application, Application.pipeline_id == Pipeline.id)
            .where(Pipeline.tenant_id == tenant_id)
            .group_by(Pipeline.id)
            .order_by(Pipeline.created_at.desc())
        )
        if status:
            stmt = stmt.where(Pipeline.status == status)
        rows = (await self.db.execute(stmt)).all()
        return [(r[0], int(r[1] or 0)) for r in rows]

    async def get_pipeline(self, tenant_id: int, pipeline_id: int) -> Pipeline | None:
        stmt = select(Pipeline).where(Pipeline.tenant_id == tenant_id, Pipeline.id == pipeline_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_pipeline(self, **kwargs) -> Pipeline:
        p = Pipeline(**kwargs)
        self.db.add(p)
        await self.db.flush()
        return p

    async def update_pipeline(self, p: Pipeline, **kwargs) -> Pipeline:
        for k, v in kwargs.items():
            if v is not None:
                setattr(p, k, v)
        await self.db.flush()
        return p

    async def delete_pipeline(self, p: Pipeline) -> None:
        await self.db.delete(p)
        await self.db.flush()

    # ─── Stages ────────────────────────────────────────
    async def list_stages(self, pipeline_id: int) -> list[Stage]:
        stmt = select(Stage).where(Stage.pipeline_id == pipeline_id).order_by(Stage.position.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_stage(self, tenant_id: int, stage_id: int) -> Stage | None:
        stmt = select(Stage).where(Stage.tenant_id == tenant_id, Stage.id == stage_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_stage(self, **kwargs) -> Stage:
        s = Stage(**kwargs)
        self.db.add(s)
        await self.db.flush()
        return s

    # ─── Candidates ────────────────────────────────────────
    async def list_candidates(
        self, tenant_id: int, search: str | None = None
    ) -> list[Candidate]:
        stmt = select(Candidate).where(Candidate.tenant_id == tenant_id)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                (func.lower(Candidate.first_name + " " + Candidate.last_name).like(like))
                | (func.lower(Candidate.email).like(like))
            )
        stmt = stmt.order_by(Candidate.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_candidate(self, tenant_id: int, candidate_id: int) -> Candidate | None:
        stmt = select(Candidate).where(
            Candidate.tenant_id == tenant_id, Candidate.id == candidate_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_candidate(self, **kwargs) -> Candidate:
        c = Candidate(**kwargs)
        self.db.add(c)
        await self.db.flush()
        return c

    async def update_candidate(self, c: Candidate, **kwargs) -> Candidate:
        for k, v in kwargs.items():
            if v is not None:
                setattr(c, k, v)
        await self.db.flush()
        return c

    # ─── Applications ────────────────────────────────────────
    async def list_applications_for_pipeline(self, pipeline_id: int) -> list[Application]:
        stmt = select(Application).where(Application.pipeline_id == pipeline_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_application(self, tenant_id: int, app_id: int) -> Application | None:
        stmt = select(Application).where(
            Application.tenant_id == tenant_id, Application.id == app_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_application(self, **kwargs) -> Application:
        a = Application(**kwargs)
        self.db.add(a)
        await self.db.flush()
        return a

    async def update_application(self, app: Application, **kwargs) -> Application:
        for k, v in kwargs.items():
            if v is not None:
                setattr(app, k, v)
        await self.db.flush()
        # Recargar columnas con onupdate server-side (p.ej. updated_at) dentro del
        # contexto async; si no, Pydantic lanza MissingGreenlet al serializarlas.
        await self.db.refresh(app)
        return app

    async def add_event(self, **kwargs) -> ApplicationEvent:
        ev = ApplicationEvent(**kwargs)
        self.db.add(ev)
        await self.db.flush()
        return ev

    async def list_events(self, app_id: int) -> list[ApplicationEvent]:
        stmt = (
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == app_id)
            .order_by(ApplicationEvent.created_at.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def latest_stage_change(self, app_id: int) -> ApplicationEvent | None:
        """Última transición de stage_change para calcular "días en stage actual"."""
        stmt = (
            select(ApplicationEvent)
            .where(
                ApplicationEvent.application_id == app_id,
                ApplicationEvent.kind == "stage_change",
            )
            .order_by(ApplicationEvent.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

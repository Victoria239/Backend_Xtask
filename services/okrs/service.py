"""OKRs service — Business logic con cascada y check-ins (C-02)."""

import logging

from shared.notifications import emit_notification
from services.okrs.models import KeyResult, Okr
from services.okrs.repository import OkrRepository
from services.okrs.schemas import (
    CheckinIn,
    KeyResultIn,
    KeyResultOut,
    KeyResultUpdate,
    OkrDetail,
    OkrIn,
    OkrOut,
    OkrTreeNode,
    OkrUpdate,
    WhatIfKr,
    WhatIfOkr,
    WhatIfRequest,
    WhatIfResponse,
)

logger = logging.getLogger(__name__)


# ─── Semáforo de status ─────────────────────────────────────────
# Más estricto que KPIs porque OKR es agregado (queremos visibilidad temprana).
# ≥100 met · ≥120 exceeded · ≥70 on-track · ≥40 at-risk · <40 off-track
def _status_from_progress(progress: float) -> str:
    if progress >= 120:
        return "exceeded"
    if progress >= 100:
        return "met"
    if progress >= 70:
        return "on-track"
    if progress >= 40:
        return "at-risk"
    return "off-track"


def _kr_progress(kr: KeyResult) -> float:
    """0..100. Si baseline == target, ya está completo."""
    target = float(kr.target)
    baseline = float(kr.baseline)
    current = float(kr.current)
    if target == baseline:
        return 100.0 if current >= target else 0.0
    pct = ((current - baseline) / (target - baseline)) * 100
    return max(0.0, min(150.0, pct))  # cap a 150 para "exceeded" sin volar


class OkrService:
    def __init__(self, repo: OkrRepository):
        self.repo = repo

    # ─── CRUD ─────────────────────────────────────────
    async def list_okrs(self, tenant_id: int, period: str | None = None) -> list[OkrOut]:
        items = await self.repo.list_okrs(tenant_id, period)
        return [OkrOut.model_validate(o) for o in items]

    async def get_okr_detail(self, tenant_id: int, okr_id: int) -> OkrDetail | None:
        okr = await self.repo.get_okr(tenant_id, okr_id)
        if not okr:
            return None
        krs = await self.repo.list_krs(okr_id)
        kr_out = [
            KeyResultOut.model_validate({**kr.__dict__, "progress": _kr_progress(kr)}) for kr in krs
        ]
        base = OkrOut.model_validate(okr).model_dump()
        return OkrDetail(**base, key_results=kr_out)

    async def create_okr(self, tenant_id: int, user_id: int | None, payload: OkrIn) -> OkrDetail:
        # Validar parent si viene
        if payload.parent_id is not None:
            parent = await self.repo.get_okr(tenant_id, payload.parent_id)
            if not parent:
                raise ValueError(f"parent_id {payload.parent_id} no existe en este tenant")

        data = payload.model_dump(exclude={"key_results"})
        data["tenant_id"] = tenant_id
        data["created_by"] = user_id
        okr = await self.repo.create_okr(**data)

        for kr_payload in payload.key_results:
            await self.repo.create_kr(
                tenant_id=tenant_id, okr_id=okr.id, **kr_payload.model_dump()
            )

        # Recalcular cascada hacia arriba
        await self._recalculate_chain(tenant_id, okr.id)
        detail = await self.get_okr_detail(tenant_id, okr.id)
        if detail is None:
            raise RuntimeError(f"OKR {okr.id} desapareció inmediatamente después de crearlo (race?)")
        return detail

    async def update_okr(self, tenant_id: int, okr_id: int, payload: OkrUpdate) -> OkrDetail | None:
        okr = await self.repo.get_okr(tenant_id, okr_id)
        if not okr:
            return None
        old_parent = okr.parent_id
        await self.repo.update_okr(okr, **payload.model_dump(exclude_unset=True))
        # Recalcular tanto la cadena vieja como la nueva si el padre cambió
        if old_parent and old_parent != okr.parent_id:
            await self._recalculate_chain(tenant_id, old_parent)
        await self._recalculate_chain(tenant_id, okr.id)
        return await self.get_okr_detail(tenant_id, okr.id)

    async def delete_okr(self, tenant_id: int, okr_id: int) -> bool:
        okr = await self.repo.get_okr(tenant_id, okr_id)
        if not okr:
            return False
        parent_id = okr.parent_id
        await self.repo.delete_okr(okr)
        if parent_id:
            await self._recalculate_chain(tenant_id, parent_id)
        return True

    # ─── Key Results ─────────────────────────────────────────
    async def add_kr(self, tenant_id: int, okr_id: int, payload: KeyResultIn) -> KeyResultOut:
        okr = await self.repo.get_okr(tenant_id, okr_id)
        if not okr:
            raise ValueError(f"OKR {okr_id} no existe en este tenant")
        kr = await self.repo.create_kr(
            tenant_id=tenant_id, okr_id=okr_id, **payload.model_dump()
        )
        await self._recalculate_chain(tenant_id, okr_id)
        return KeyResultOut.model_validate({**kr.__dict__, "progress": _kr_progress(kr)})

    async def update_kr(self, tenant_id: int, kr_id: int, payload: KeyResultUpdate) -> KeyResultOut | None:
        kr = await self.repo.get_kr(tenant_id, kr_id)
        if not kr:
            return None
        await self.repo.update_kr(kr, **payload.model_dump(exclude_unset=True))
        await self._recalculate_chain(tenant_id, kr.okr_id)
        return KeyResultOut.model_validate({**kr.__dict__, "progress": _kr_progress(kr)})

    async def delete_kr(self, tenant_id: int, kr_id: int) -> bool:
        kr = await self.repo.get_kr(tenant_id, kr_id)
        if not kr:
            return False
        okr_id = kr.okr_id
        await self.repo.delete_kr(kr)
        await self._recalculate_chain(tenant_id, okr_id)
        return True

    # ─── Check-in (manual o auto) ─────────────────────────────────────────
    async def checkin(
        self,
        tenant_id: int,
        user_id: int | None,
        payload: CheckinIn,
        source: str = "manual",
    ) -> KeyResultOut:
        kr = await self.repo.get_kr(tenant_id, payload.kr_id)
        if not kr:
            raise ValueError(f"KR {payload.kr_id} no existe en este tenant")

        await self.repo.add_checkin(
            tenant_id=tenant_id,
            kr_id=kr.id,
            value=payload.value,
            confidence=payload.confidence,
            comment=payload.comment,
            source=source,
            created_by=user_id,
        )
        await self.repo.update_kr_current(kr.id, payload.value)
        kr.current = payload.value
        await self._recalculate_chain(tenant_id, kr.okr_id)
        return KeyResultOut.model_validate({**kr.__dict__, "progress": _kr_progress(kr)})

    # ─── Cascade & status ─────────────────────────────────────────
    async def _recalculate_okr(self, tenant_id: int, okr_id: int) -> tuple[float, str, str]:
        """Recalcula progress + status para un OKR.

        Mezcla los KR propios (ponderados) con los OKRs hijos (cascada).
        Devuelve (progress, new_status, old_status) para emitir notif si hubo crossing.
        """
        okr = await self.repo.get_okr(tenant_id, okr_id)
        if not okr:
            return 0.0, "off-track", "off-track"
        old_status = okr.status

        # 1. Progreso propio (KRs directos)
        krs = await self.repo.list_krs(okr_id)
        own_total_w = sum(float(kr.weight) for kr in krs) or 0.0
        own_progress = (
            sum(_kr_progress(kr) * float(kr.weight) for kr in krs) / own_total_w
            if own_total_w > 0
            else None
        )

        # 2. Progreso agregado de hijos directos
        children = await self.repo.list_okrs(tenant_id)
        children = [c for c in children if c.parent_id == okr_id]
        child_total_w = sum(float(c.weight) for c in children) or 0.0
        child_progress = (
            sum(float(c.progress) * float(c.weight) for c in children) / child_total_w
            if child_total_w > 0
            else None
        )

        # 3. Combinar — 50/50 si hay ambos, sino el que exista, sino 0
        if own_progress is not None and child_progress is not None:
            progress = (own_progress + child_progress) / 2
        elif own_progress is not None:
            progress = own_progress
        elif child_progress is not None:
            progress = child_progress
        else:
            progress = 0.0

        progress = round(progress, 2)
        new_status = _status_from_progress(progress)
        await self.repo.update_metrics(okr_id, progress, new_status)
        return progress, new_status, old_status

    async def _recalculate_chain(self, tenant_id: int, leaf_okr_id: int) -> None:
        """Recalcula hacia arriba: la hoja, su padre, abuelo, etc."""
        try:
            from shared.metrics import OKR_RECALCULATIONS
            OKR_RECALCULATIONS.labels(tenant_id=str(tenant_id)).inc()
        except Exception:  # noqa: BLE001
            pass
        current_id: int | None = leaf_okr_id
        visited: set[int] = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            okr = await self.repo.get_okr(tenant_id, current_id)
            if not okr:
                break
            _, new_status, old_status = await self._recalculate_okr(tenant_id, current_id)

            # P-04: alertas en crossing a riesgo
            if new_status in ("at-risk", "off-track") and new_status != old_status:
                await self._emit_alert(tenant_id, okr, new_status)

            current_id = okr.parent_id

    async def _emit_alert(self, tenant_id: int, okr: Okr, status: str) -> None:
        """Notifica al owner del OKR cuando cruza a estado crítico."""
        try:
            user_id = None
            if okr.owner_employee_id:
                from sqlalchemy import text  # local import to avoid leaking dep at module load
                row = (await self.repo.db.execute(
                    text("SELECT user_id FROM svc_employees.employees WHERE id = :eid AND tenant_id = :tid LIMIT 1"),
                    {"eid": okr.owner_employee_id, "tid": tenant_id},
                )).first()
                if row and row[0]:
                    user_id = int(row[0])

            if not user_id:
                return  # company-wide u objetivos sin owner → no spammeamos, los ven en el dashboard

            kind = "warning" if status == "at-risk" else "error"
            label = "en riesgo" if status == "at-risk" else "fuera de curso"
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id,
                user_id=user_id,
                title=f'OKR "{okr.objective}" {label}',
                body=f"El cumplimiento de tu OKR del periodo {okr.period} cruzó a {status}. Revisá los key results.",
                kind=kind,
                category="okrs",
                action_url="/okrs",
                meta={"okr_id": okr.id, "status": status, "period": okr.period},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("okr_alert_failed", exc_info=e)

    # ─── Cascade tree view ─────────────────────────────────────────
    async def get_cascade(self, tenant_id: int, period: str | None = None) -> list[OkrTreeNode]:
        items = await self.repo.list_okrs(tenant_id, period)
        # Agrupar KRs por OKR en una sola pasada
        nodes_by_id: dict[int, OkrTreeNode] = {}
        for o in items:
            krs = await self.repo.list_krs(o.id)
            kr_out = [
                KeyResultOut.model_validate({**kr.__dict__, "progress": _kr_progress(kr)})
                for kr in krs
            ]
            base = OkrOut.model_validate(o).model_dump()
            nodes_by_id[o.id] = OkrTreeNode(**base, key_results=kr_out, children=[])

        roots: list[OkrTreeNode] = []
        for o in items:
            node = nodes_by_id[o.id]
            if o.parent_id and o.parent_id in nodes_by_id:
                nodes_by_id[o.parent_id].children.append(node)
            else:
                roots.append(node)
        return roots

    # ─── What-if (AI-07) ─────────────────────────────────────────
    async def whatif(
        self, tenant_id: int, period: str | None, payload: WhatIfRequest,
    ) -> WhatIfResponse:
        """Simula el efecto de modificar el current de varios KRs sin persistir.

        Pasos:
          1. Cargar el árbol actual (todos los OKRs + KRs del período).
          2. Aplicar overrides en una copia en memoria.
          3. Recalcular cascada bottom-up.
          4. Devolver diff afectado (OKRs y KRs que cambiaron de progress o status).
        """
        okrs = await self.repo.list_okrs(tenant_id, period)
        all_krs: list = []
        for o in okrs:
            all_krs.extend(await self.repo.list_krs(o.id))

        # Snapshot de "current" original de cada KR
        original_current: dict[int, float] = {kr.id: float(kr.current) for kr in all_krs}
        original_progress: dict[int, float] = {kr.id: _kr_progress(kr) for kr in all_krs}

        # Aplicar overrides en memoria (modifico el objeto pero NO persisto)
        sim_current: dict[int, float] = dict(original_current)
        for kr in all_krs:
            if kr.id in payload.kr_overrides:
                sim_current[kr.id] = float(payload.kr_overrides[kr.id])

        # Helper: progress simulado de un KR (sin tocar la DB)
        def kr_sim_progress(kr) -> float:
            target = float(kr.target)
            baseline = float(kr.baseline)
            current = sim_current[kr.id]
            if target == baseline:
                return 100.0 if current >= target else 0.0
            pct = ((current - baseline) / (target - baseline)) * 100
            return max(0.0, min(150.0, pct))

        # Calcular progress simulado bottom-up
        krs_by_okr: dict[int, list] = {}
        for kr in all_krs:
            krs_by_okr.setdefault(kr.okr_id, []).append(kr)

        children_by_parent: dict[int, list] = {}
        for o in okrs:
            if o.parent_id:
                children_by_parent.setdefault(o.parent_id, []).append(o)

        sim_progress_by_okr: dict[int, float] = {}

        def recurse(okr) -> float:
            # progress propio (de los KRs directos)
            krs = krs_by_okr.get(okr.id, [])
            own_total_w = sum(float(kr.weight) for kr in krs) or 0.0
            own_progress = (
                sum(kr_sim_progress(kr) * float(kr.weight) for kr in krs) / own_total_w
                if own_total_w > 0 else None
            )
            # progress agregado de hijos
            children = children_by_parent.get(okr.id, [])
            child_total_w = sum(float(c.weight) for c in children) or 0.0
            child_progress = (
                sum(recurse(c) * float(c.weight) for c in children) / child_total_w
                if child_total_w > 0 else None
            )
            # combinar 50/50 si ambos, sino el único
            if own_progress is not None and child_progress is not None:
                p = (own_progress + child_progress) / 2
            elif own_progress is not None:
                p = own_progress
            elif child_progress is not None:
                p = child_progress
            else:
                p = 0.0
            p = round(p, 2)
            sim_progress_by_okr[okr.id] = p
            return p

        roots = [o for o in okrs if not o.parent_id]
        for r in roots:
            recurse(r)
        # También procesar hijos huérfanos (parent no encontrado)
        for o in okrs:
            if o.id not in sim_progress_by_okr:
                recurse(o)

        # Build response — solo OKRs y KRs afectados
        affected_okrs: list[WhatIfOkr] = []
        for o in okrs:
            sim_p = sim_progress_by_okr.get(o.id, float(o.progress))
            cur_p = float(o.progress)
            if abs(sim_p - cur_p) < 0.01:
                continue
            affected_okrs.append(WhatIfOkr(
                id=o.id, parent_id=o.parent_id,
                objective=o.objective, scope=o.scope, period=o.period,
                current_progress=cur_p, current_status=o.status,
                sim_progress=sim_p, sim_status=_status_from_progress(sim_p),
                delta_progress=round(sim_p - cur_p, 2),
            ))

        affected_krs: list[WhatIfKr] = []
        for kr in all_krs:
            if kr.id not in payload.kr_overrides:
                continue
            new_p = kr_sim_progress(kr)
            affected_krs.append(WhatIfKr(
                id=kr.id, okr_id=kr.okr_id, name=kr.name,
                baseline=float(kr.baseline), target=float(kr.target),
                current=float(kr.current), sim_current=sim_current[kr.id],
                current_progress=original_progress[kr.id], sim_progress=new_p,
            ))

        return WhatIfResponse(
            period=period, affected_okrs=affected_okrs, affected_krs=affected_krs,
        )

    # ─── Auto check-in desde KPI ─────────────────────────────────────────
    async def auto_checkin_from_kpi(
        self, tenant_id: int, kpi_id: int, kpi_actual_value: float
    ) -> int:
        """Propaga el valor actual de un KPI a todos los KRs vinculados. Retorna #KRs actualizados."""
        krs = await self.repo.find_krs_by_linked_kpi(tenant_id, kpi_id)
        if not krs:
            return 0
        for kr in krs:
            await self.repo.add_checkin(
                tenant_id=tenant_id, kr_id=kr.id, value=kpi_actual_value,
                confidence=None, comment=None, source="kpi-auto", created_by=None,
            )
            await self.repo.update_kr_current(kr.id, kpi_actual_value)
            kr.current = kpi_actual_value
            await self._recalculate_chain(tenant_id, kr.okr_id)
        return len(krs)

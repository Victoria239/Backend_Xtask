"""Leaves service — business logic (H-04).

State machine:
    requested → approved → taken
              → rejected
              → cancelled (desde requested o approved)

Cálculo de business_days: días entre start y end exclusivo de fines de semana.
Festivos por tenant podrían cargarse desde una tabla holiday — para MVP solo S/D.
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import text

from shared.notifications import emit_notification
from services.leaves.models import Leave, LeaveBalance, LeaveType
from services.leaves.repository import LeavesRepository
from services.leaves.schemas import (
    BalanceAdjustment, BalanceOut, LeaveDecision, LeaveEventOut, LeaveIn,
    LeaveOut, LeaveSummary, LeaveTypeIn, LeaveTypeOut, LeaveUpdate,
)

logger = logging.getLogger(__name__)


# ─── Transiciones legales ───────────────────────────────
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "requested": {"approved", "rejected", "cancelled"},
    "approved": {"cancelled", "taken"},
    "rejected": set(),
    "cancelled": set(),
    "taken": set(),
}


def _count_business_days(start: date, end: date) -> int:
    """Días hábiles entre start y end inclusivo. Excluye sábados y domingos."""
    if end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # 0..4 = Mon..Fri
            days += 1
        cur += timedelta(days=1)
    return days


class LeavesService:
    def __init__(self, repo: LeavesRepository):
        self.repo = repo

    # ─── Types CRUD ─────────────────────────────────────────
    async def list_types(self, tenant_id: int) -> list[LeaveTypeOut]:
        items = await self.repo.list_types(tenant_id, active_only=False)
        return [LeaveTypeOut.model_validate(t) for t in items]

    async def create_type(self, tenant_id: int, payload: LeaveTypeIn) -> LeaveTypeOut:
        data = payload.model_dump()
        data["tenant_id"] = tenant_id
        lt = await self.repo.create_type(**data)
        return LeaveTypeOut.model_validate(lt)

    async def update_type(self, tenant_id: int, type_id: int, payload: LeaveTypeIn) -> LeaveTypeOut | None:
        lt = await self.repo.get_type(tenant_id, type_id)
        if not lt:
            return None
        await self.repo.update_type(lt, **payload.model_dump())
        return LeaveTypeOut.model_validate(lt)

    # ─── Solicitud de ausencia ─────────────────────────────────────────
    async def request_leave(
        self, tenant_id: int, employee_id: int, user_id: int | None, payload: LeaveIn
    ) -> LeaveOut:
        lt = await self.repo.get_type(tenant_id, payload.type_id)
        if not lt:
            raise ValueError("Tipo de ausencia no existe")
        if not lt.active:
            raise ValueError("El tipo de ausencia está deshabilitado")

        if payload.end_date < payload.start_date:
            raise ValueError("end_date debe ser >= start_date")

        bd = _count_business_days(payload.start_date, payload.end_date)
        if bd == 0:
            raise ValueError("La solicitud no cubre ningún día hábil")

        # Validar saldo (excepto en tipos sin saldo: enfermedad, unlimited)
        if lt.accrual_strategy != "unlimited":
            balance = await self._compute_available(
                tenant_id, employee_id, lt, year=payload.start_date.year
            )
            if balance < bd and not lt.allow_negative_balance:
                raise ValueError(
                    f"Saldo insuficiente: disponibles {balance:.1f}, solicitados {bd}"
                )

        initial_status = "requested" if lt.requires_approval else "approved"

        leave = await self.repo.create_leave(
            tenant_id=tenant_id,
            employee_id=employee_id,
            type_id=lt.id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            business_days=bd,
            status=initial_status,
            reason=payload.reason,
            requested_by=user_id,
            decided_by=user_id if initial_status == "approved" else None,
            decided_at=datetime.utcnow() if initial_status == "approved" else None,
        )
        await self.repo.add_event(
            tenant_id=tenant_id, leave_id=leave.id,
            from_status=None, to_status=initial_status,
            actor_user_id=user_id,
            note="Solicitud creada" if initial_status == "requested" else "Auto-aprobada (tipo sin aprobación)",
        )

        # Recalcular balance + notificar
        await self._recalc_balance(tenant_id, employee_id, lt.id, payload.start_date.year)
        await self._notify_request(tenant_id, leave, lt)
        return await self._to_out(tenant_id, leave)

    async def update_leave(
        self, tenant_id: int, leave_id: int, payload: LeaveUpdate
    ) -> LeaveOut | None:
        leave = await self.repo.get_leave(tenant_id, leave_id)
        if not leave:
            return None
        if leave.status not in ("requested", "approved"):
            raise ValueError("Solo se pueden editar solicitudes en requested o approved")

        updates = payload.model_dump(exclude_unset=True)
        if "start_date" in updates or "end_date" in updates:
            new_start = updates.get("start_date") or leave.start_date
            new_end = updates.get("end_date") or leave.end_date
            if new_end < new_start:
                raise ValueError("end_date debe ser >= start_date")
            updates["business_days"] = _count_business_days(new_start, new_end)

        await self.repo.update_leave(leave, **updates)
        await self._recalc_balance(tenant_id, leave.employee_id, leave.type_id, leave.start_date.year)
        return await self._to_out(tenant_id, leave)

    async def decide(
        self, tenant_id: int, leave_id: int, user_id: int | None, payload: LeaveDecision
    ) -> LeaveOut:
        leave = await self.repo.get_leave(tenant_id, leave_id)
        if not leave:
            raise ValueError("Solicitud no encontrada")
        if leave.status != "requested":
            raise ValueError(f"Solo se decide sobre solicitudes en requested (estado actual: {leave.status})")

        new_status = payload.decision  # approved | rejected
        if new_status not in ALLOWED_TRANSITIONS.get(leave.status, set()):
            raise ValueError(f"Transición ilegal: {leave.status} → {new_status}")

        old_status = leave.status
        await self.repo.update_leave(
            leave, status=new_status, approval_note=payload.note,
            decided_by=user_id, decided_at=datetime.utcnow(),
        )
        await self.repo.add_event(
            tenant_id=tenant_id, leave_id=leave.id,
            from_status=old_status, to_status=new_status,
            actor_user_id=user_id, note=payload.note,
        )
        await self._recalc_balance(tenant_id, leave.employee_id, leave.type_id, leave.start_date.year)
        await self._notify_decision(tenant_id, leave, new_status)

        try:
            from shared.n8n_client import emit_event
            await emit_event(f"xtask.leave.{new_status}", {
                "tenant_id": tenant_id,
                "leave_id": leave.id,
                "employee_id": leave.employee_id,
                "start_date": str(leave.start_date),
                "end_date": str(leave.end_date),
                "business_days": float(leave.business_days or 0),
            })
        except Exception:  # noqa: BLE001
            pass

        return await self._to_out(tenant_id, leave)

    async def cancel(
        self, tenant_id: int, leave_id: int, user_id: int | None
    ) -> LeaveOut:
        leave = await self.repo.get_leave(tenant_id, leave_id)
        if not leave:
            raise ValueError("Solicitud no encontrada")
        if leave.status not in ("requested", "approved"):
            raise ValueError(f"Solo se cancelan solicitudes en requested o approved (estado: {leave.status})")

        old_status = leave.status
        await self.repo.update_leave(leave, status="cancelled")
        await self.repo.add_event(
            tenant_id=tenant_id, leave_id=leave.id,
            from_status=old_status, to_status="cancelled",
            actor_user_id=user_id,
        )
        await self._recalc_balance(tenant_id, leave.employee_id, leave.type_id, leave.start_date.year)
        return await self._to_out(tenant_id, leave)

    # ─── Balance computation ─────────────────────────────────────────
    async def _compute_available(
        self, tenant_id: int, employee_id: int, lt: LeaveType, year: int
    ) -> float:
        bal = await self.repo.get_balance(tenant_id, employee_id, lt.id, year)
        if not bal:
            # Crear con devengo inicial
            bal = await self.repo.upsert_balance(
                tenant_id=tenant_id, employee_id=employee_id, type_id=lt.id, year=year,
                accrued=float(lt.days_per_year), used=0, pending=0, adjustments=0,
            )
        return (
            float(bal.accrued) + float(bal.adjustments)
            - float(bal.used) - float(bal.pending)
        )

    async def _recalc_balance(
        self, tenant_id: int, employee_id: int, type_id: int, year: int
    ) -> None:
        """Reagrega los días usados / pending de un empleado en el año."""
        # Sumar pending (requested) y used (approved + taken)
        row = (await self.repo.db.execute(
            text(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status='requested' THEN business_days ELSE 0 END), 0) AS pending,
                    COALESCE(SUM(CASE WHEN status IN ('approved','taken') THEN business_days ELSE 0 END), 0) AS used
                FROM svc_leaves.leaves
                WHERE tenant_id = :tid
                  AND employee_id = :eid
                  AND type_id = :ttid
                  AND EXTRACT(YEAR FROM start_date) = :y
                """
            ),
            {"tid": tenant_id, "eid": employee_id, "ttid": type_id, "y": year},
        )).first()
        pending = float(row[0]) if row else 0.0
        used = float(row[1]) if row else 0.0

        bal = await self.repo.get_balance(tenant_id, employee_id, type_id, year)
        if bal is None:
            # Crear con default — devengo según tipo
            lt = await self.repo.get_type(tenant_id, type_id)
            initial = float(lt.days_per_year) if lt and lt.accrual_strategy == "annual_grant" else 0
            await self.repo.upsert_balance(
                tenant_id=tenant_id, employee_id=employee_id, type_id=type_id, year=year,
                accrued=initial, used=used, pending=pending, adjustments=0,
            )
        else:
            bal.used = used
            bal.pending = pending
            await self.repo.db.flush()

    async def list_balances(
        self, tenant_id: int, employee_id: int, year: int
    ) -> list[BalanceOut]:
        """Devuelve todos los balances del empleado con info del tipo."""
        # Asegurar que el empleado tiene balance por cada tipo activo (lazy init)
        types = await self.repo.list_types(tenant_id, active_only=True)
        for lt in types:
            if lt.accrual_strategy == "unlimited":
                continue
            await self._recalc_balance(tenant_id, employee_id, lt.id, year)

        balances = await self.repo.list_balances_for_employee(tenant_id, employee_id, year)
        types_by_id = {t.id: t for t in types}
        out = []
        for b in balances:
            lt = types_by_id.get(b.type_id)
            if not lt:
                continue
            available = (
                float(b.accrued) + float(b.adjustments)
                - float(b.used) - float(b.pending)
            )
            out.append(BalanceOut(
                id=b.id, employee_id=b.employee_id, type_id=b.type_id,
                type_name=lt.name, type_color=lt.color, year=b.year,
                accrued=float(b.accrued), used=float(b.used), pending=float(b.pending),
                adjustments=float(b.adjustments), available=available,
                last_computed_at=b.last_computed_at,
            ))
        return out

    async def adjust_balance(
        self, tenant_id: int, employee_id: int, type_id: int, year: int,
        payload: BalanceAdjustment, actor_user_id: int | None,
    ) -> BalanceOut:
        bal = await self.repo.get_balance(tenant_id, employee_id, type_id, year)
        if not bal:
            await self._recalc_balance(tenant_id, employee_id, type_id, year)
            bal = await self.repo.get_balance(tenant_id, employee_id, type_id, year)
        if not bal:
            raise ValueError("No se pudo obtener el balance")
        bal.adjustments = float(bal.adjustments) + payload.delta
        await self.repo.db.flush()
        # Recargar tipo para enriquecer la respuesta
        lt = await self.repo.get_type(tenant_id, type_id)
        available = (
            float(bal.accrued) + float(bal.adjustments)
            - float(bal.used) - float(bal.pending)
        )
        return BalanceOut(
            id=bal.id, employee_id=bal.employee_id, type_id=bal.type_id,
            type_name=lt.name if lt else "?", type_color=lt.color if lt else "#888",
            year=bal.year, accrued=float(bal.accrued), used=float(bal.used),
            pending=float(bal.pending), adjustments=float(bal.adjustments),
            available=available, last_computed_at=bal.last_computed_at,
        )

    # ─── Notifs ─────────────────────────────────────────
    async def _notify_request(self, tenant_id: int, leave: Leave, lt: LeaveType) -> None:
        if not lt.requires_approval:
            return
        manager_uid = await self.repo.get_employee_manager_user(tenant_id, leave.employee_id)
        if not manager_uid:
            return
        _, name = await self.repo.get_employee_user(tenant_id, leave.employee_id)
        try:
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id, user_id=manager_uid,
                title=f"Solicitud de {lt.name.lower()} de {name}",
                body=f"{leave.business_days:.0f} días desde {leave.start_date} a {leave.end_date}",
                kind="info", category="leaves",
                action_url=f"/ausencias/{leave.id}",
                meta={"leave_id": leave.id, "type_code": lt.code},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("leave_request_notif_failed", exc_info=e)

    async def _notify_decision(self, tenant_id: int, leave: Leave, status: str) -> None:
        user_id, _ = await self.repo.get_employee_user(tenant_id, leave.employee_id)
        if not user_id:
            return
        try:
            await emit_notification(
                self.repo.db,
                tenant_id=tenant_id, user_id=user_id,
                title=f"Tu solicitud fue {'aprobada' if status == 'approved' else 'rechazada'}",
                body=f"Solicitud #{leave.id} de {leave.business_days:.0f} días.",
                kind="success" if status == "approved" else "warning",
                category="leaves",
                action_url=f"/ausencias/{leave.id}",
                meta={"leave_id": leave.id, "status": status},
                email=True,  # P-04.2
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("leave_decision_notif_failed", exc_info=e)

    # ─── Helpers para respuestas enriquecidas ────────────
    async def _to_out(self, tenant_id: int, leave: Leave) -> LeaveOut:
        lt = await self.repo.get_type(tenant_id, leave.type_id)
        base = LeaveOut.model_validate(leave).model_dump()
        base["type_name"] = lt.name if lt else None
        return LeaveOut(**base)

    async def list_leaves(
        self, tenant_id: int, **filters
    ) -> list[LeaveSummary]:
        items = await self.repo.list_leaves(tenant_id, **filters)
        types = {t.id: t for t in await self.repo.list_types(tenant_id, active_only=False)}
        out = []
        for l in items:
            t = types.get(l.type_id)
            out.append(LeaveSummary(
                id=l.id, employee_id=l.employee_id, type_id=l.type_id,
                type_name=t.name if t else "?", type_color=t.color if t else "#888",
                start_date=l.start_date, end_date=l.end_date,
                business_days=float(l.business_days),
                status=l.status, created_at=l.created_at,
            ))
        return out

    async def list_events(self, tenant_id: int, leave_id: int) -> list[LeaveEventOut]:
        leave = await self.repo.get_leave(tenant_id, leave_id)
        if not leave:
            raise ValueError("Solicitud no encontrada")
        evs = await self.repo.list_events(leave_id)
        return [LeaveEventOut.model_validate(e) for e in evs]

    async def get_leave(self, tenant_id: int, leave_id: int) -> LeaveOut | None:
        leave = await self.repo.get_leave(tenant_id, leave_id)
        if not leave:
            return None
        return await self._to_out(tenant_id, leave)

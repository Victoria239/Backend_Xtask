"""Admin dashboard endpoints (P-03).

Vista super-admin: lista tenants con métricas agregadas cross-schema.
Permite suspender/reactivar tenants y ver auditoría básica.

Requiere rol admin. En producción se restringirá además a un realm separado
"xtask-superadmin" para que los admins de tenants no puedan ver otros.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import require_admin

router = APIRouter()


class TenantStats(BaseModel):
    id: int
    slug: str
    name: str
    plan: str
    is_active: bool
    domain: str | None
    created_at: datetime
    # Métricas
    employees_total: int
    employees_active: int
    documents: int
    contracts_total: int
    contracts_active: int
    okrs: int
    kpis: int
    last_activity_at: datetime | None
    # Billing approx
    plan_limit_employees: int | None
    plan_monthly_cost_eur: float


class TenantAdminDetail(TenantStats):
    notifications_30d: int
    payouts_30d_total: float
    pipelines_open: int


class SuspendRequest(BaseModel):
    reason: str | None = None


# Pricing aproximado por plan (placeholder hasta que conectemos billing real)
PLAN_CONFIG = {
    "startup": {"limit_employees": 25, "monthly_cost_eur": 99.0},
    "growth": {"limit_employees": 100, "monthly_cost_eur": 299.0},
    "scale": {"limit_employees": 500, "monthly_cost_eur": 999.0},
    "enterprise": {"limit_employees": None, "monthly_cost_eur": 2500.0},
}


@router.get("/admin/dashboard", response_model=list[TenantStats], dependencies=[Depends(require_admin)])
async def admin_dashboard(
    db: AsyncSession = Depends(get_service_db("tenants")),
):
    """Lista todos los tenants con métricas agregadas."""
    # 1) tenants base
    tenants = (await db.execute(
        text("SELECT id, slug, name, plan, is_active, domain, created_at FROM svc_tenants.tenants ORDER BY created_at ASC")
    )).all()

    out: list[TenantStats] = []
    for t in tenants:
        t_id = int(t[0])
        # Cross-schema aggregations — todas defensivas para que un schema faltante no rompa el endpoint
        emp_row = (await db.execute(
            text(
                "SELECT COUNT(*), COUNT(*) FILTER (WHERE contract_status = 'active') "
                "FROM svc_employees.employees WHERE tenant_id = :tid"
            ),
            {"tid": t_id},
        )).first()
        emp_total = int(emp_row[0] or 0) if emp_row else 0
        emp_active = int(emp_row[1] or 0) if emp_row else 0

        async def _safe_count(sql: str, params: dict) -> int:
            try:
                row = (await db.execute(text(sql), params)).first()
                return int(row[0] or 0) if row else 0
            except Exception:  # noqa: BLE001
                return 0

        docs = await _safe_count("SELECT COUNT(*) FROM svc_rag.documents WHERE tenant_id = :tid", {"tid": t_id})
        ctr_total = await _safe_count("SELECT COUNT(*) FROM svc_contracts.contracts WHERE tenant_id = :tid", {"tid": t_id})
        ctr_active = await _safe_count(
            "SELECT COUNT(*) FROM svc_contracts.contracts WHERE tenant_id = :tid AND status IN ('draft','review','signed')",
            {"tid": t_id},
        )
        okrs = await _safe_count("SELECT COUNT(*) FROM svc_okrs.okrs WHERE tenant_id = :tid", {"tid": t_id})
        kpis = await _safe_count("SELECT COUNT(*) FROM svc_kpis.kpis WHERE tenant_id = :tid OR tenant_id IS NULL", {"tid": t_id})

        # last activity: max created_at across notifications + contracts events
        last_act_row = (await db.execute(
            text(
                """
                SELECT MAX(t) FROM (
                  SELECT MAX(created_at) AS t FROM svc_notifications.notifications WHERE tenant_id = :tid
                  UNION ALL
                  SELECT MAX(created_at) FROM svc_contracts.contract_events WHERE tenant_id = :tid
                  UNION ALL
                  SELECT MAX(updated_at) FROM svc_employees.employees WHERE tenant_id = :tid
                ) sub
                """
            ),
            {"tid": t_id},
        )).first()
        last_act = last_act_row[0] if last_act_row else None

        plan = str(t[3] or "startup")
        plan_cfg = PLAN_CONFIG.get(plan, PLAN_CONFIG["startup"])

        out.append(TenantStats(
            id=t_id, slug=str(t[1]), name=str(t[2]),
            plan=plan, is_active=bool(t[4]), domain=t[5],
            created_at=t[6],
            employees_total=emp_total, employees_active=emp_active,
            documents=docs, contracts_total=ctr_total, contracts_active=ctr_active,
            okrs=okrs, kpis=kpis,
            last_activity_at=last_act,
            plan_limit_employees=plan_cfg["limit_employees"],
            plan_monthly_cost_eur=plan_cfg["monthly_cost_eur"],
        ))
    return out


@router.get(
    "/admin/{tenant_id}/detail",
    response_model=TenantAdminDetail,
    dependencies=[Depends(require_admin)],
)
async def tenant_detail(
    tenant_id: int,
    db: AsyncSession = Depends(get_service_db("tenants")),
):
    t = (await db.execute(
        text("SELECT id, slug, name, plan, is_active, domain, created_at FROM svc_tenants.tenants WHERE id = :id"),
        {"id": tenant_id},
    )).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Re-uso lógica del dashboard con un poco más
    cutoff = datetime.utcnow() - timedelta(days=30)

    async def _safe_first(sql: str, params: dict, default):
        try:
            row = (await db.execute(text(sql), params)).first()
            return row[0] if row else default
        except Exception:  # noqa: BLE001
            return default

    notifs_30d = await _safe_first(
        "SELECT COUNT(*) FROM svc_notifications.notifications WHERE tenant_id = :tid AND created_at >= :c",
        {"tid": tenant_id, "c": cutoff}, 0,
    )
    payouts_total = await _safe_first(
        "SELECT COALESCE(SUM(total_amount), 0) FROM svc_payouts.payout_runs "
        "WHERE tenant_id = :tid AND created_at >= :c",
        {"tid": tenant_id, "c": cutoff}, 0,
    )
    pipelines_open = await _safe_first(
        "SELECT COUNT(*) FROM svc_ats.pipelines WHERE tenant_id = :tid AND status = 'open'",
        {"tid": tenant_id}, 0,
    )

    emp_row = (await db.execute(
        text(
            "SELECT COUNT(*), COUNT(*) FILTER (WHERE contract_status = 'active') "
            "FROM svc_employees.employees WHERE tenant_id = :tid"
        ),
        {"tid": tenant_id},
    )).first()
    emp_total = int(emp_row[0] or 0) if emp_row else 0
    emp_active = int(emp_row[1] or 0) if emp_row else 0

    async def _safe_count(sql: str) -> int:
        try:
            row = (await db.execute(text(sql), {"tid": tenant_id})).first()
            return int(row[0] or 0) if row else 0
        except Exception:  # noqa: BLE001
            return 0

    docs = await _safe_count("SELECT COUNT(*) FROM svc_rag.documents WHERE tenant_id = :tid")
    ctr_total = await _safe_count("SELECT COUNT(*) FROM svc_contracts.contracts WHERE tenant_id = :tid")
    ctr_active = await _safe_count(
        "SELECT COUNT(*) FROM svc_contracts.contracts WHERE tenant_id = :tid AND status IN ('draft','review','signed')"
    )
    okrs = await _safe_count("SELECT COUNT(*) FROM svc_okrs.okrs WHERE tenant_id = :tid")
    kpis = await _safe_count("SELECT COUNT(*) FROM svc_kpis.kpis WHERE tenant_id = :tid OR tenant_id IS NULL")

    plan = str(t[3] or "startup")
    plan_cfg = PLAN_CONFIG.get(plan, PLAN_CONFIG["startup"])

    return TenantAdminDetail(
        id=int(t[0]), slug=str(t[1]), name=str(t[2]),
        plan=plan, is_active=bool(t[4]), domain=t[5], created_at=t[6],
        employees_total=emp_total, employees_active=emp_active,
        documents=docs, contracts_total=ctr_total, contracts_active=ctr_active,
        okrs=okrs, kpis=kpis,
        last_activity_at=None,
        plan_limit_employees=plan_cfg["limit_employees"],
        plan_monthly_cost_eur=plan_cfg["monthly_cost_eur"],
        notifications_30d=int(notifs_30d or 0),
        payouts_30d_total=float(payouts_total or 0),
        pipelines_open=int(pipelines_open or 0),
    )


@router.post("/admin/{tenant_id}/suspend", dependencies=[Depends(require_admin)])
async def suspend_tenant(
    tenant_id: int,
    payload: SuspendRequest,
    db: AsyncSession = Depends(get_service_db("tenants")),
):
    res = await db.execute(
        text("UPDATE svc_tenants.tenants SET is_active = false, updated_at = NOW() WHERE id = :id RETURNING id"),
        {"id": tenant_id},
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {"id": int(row[0]), "is_active": False, "reason": payload.reason}


@router.post("/admin/{tenant_id}/reactivate", dependencies=[Depends(require_admin)])
async def reactivate_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_service_db("tenants")),
):
    res = await db.execute(
        text("UPDATE svc_tenants.tenants SET is_active = true, updated_at = NOW() WHERE id = :id RETURNING id"),
        {"id": tenant_id},
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {"id": int(row[0]), "is_active": True}


@router.put("/admin/{tenant_id}/plan", dependencies=[Depends(require_admin)])
async def change_plan(
    tenant_id: int,
    plan: str,
    db: AsyncSession = Depends(get_service_db("tenants")),
):
    if plan not in PLAN_CONFIG:
        raise HTTPException(status_code=400, detail=f"Plan inválido. Opciones: {list(PLAN_CONFIG.keys())}")
    res = await db.execute(
        text("UPDATE svc_tenants.tenants SET plan = :plan, updated_at = NOW() WHERE id = :id RETURNING id"),
        {"id": tenant_id, "plan": plan},
    )
    row = res.first()
    if not row:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return {"id": int(row[0]), "plan": plan}

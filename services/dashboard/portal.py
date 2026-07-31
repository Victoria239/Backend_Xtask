"""Self-service employee portal (H-06).

Agrega TODO lo que un empleado quiere ver de sí mismo en una sola payload:
- perfil + manager + reports directos
- contratos personales
- ausencias: balance + últimas 5
- reviews 360° pendientes (donde es reviewer)
- beneficios recomendados (top 3 vía motor C-05/AI-05)
- OKRs asignados como owner individual

Best-effort: cada bloque se carga en su propio try/except. Si falla uno,
los demás llegan igual.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _safe(coro):
    try:
        return await coro
    except Exception:  # noqa: BLE001
        return None


async def _profile(db: AsyncSession, tenant_id: int, user_id: int) -> dict | None:
    row = (await db.execute(text(
        "SELECT e.id, e.first_name, e.last_name, e.position, e.department, "
        "  e.hire_date, e.manager_id, e.salary, "
        "  m.first_name AS manager_first, m.last_name AS manager_last "
        "FROM svc_employees.employees e "
        "LEFT JOIN svc_employees.employees m ON m.id = e.manager_id AND m.tenant_id = e.tenant_id "
        "WHERE e.tenant_id = :t AND e.user_id = :u"
    ), {"t": tenant_id, "u": user_id})).mappings().first()
    if not row:
        return None
    return dict(row)


async def _reports(db: AsyncSession, tenant_id: int, employee_id: int) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, first_name, last_name, position "
        "FROM svc_employees.employees "
        "WHERE tenant_id = :t AND manager_id = :mid "
        "AND COALESCE(contract_status, 'active') = 'active' "
        "ORDER BY last_name, first_name"
    ), {"t": tenant_id, "mid": employee_id})).mappings().all()
    return [dict(r) for r in rows]


async def _my_contracts(db: AsyncSession, tenant_id: int, employee_id: int) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, title, contract_type, status, starts_on, expires_on, signed_on "
        "FROM svc_contracts.contracts "
        "WHERE tenant_id = :t AND employee_id = :eid AND counterparty IS NULL "
        "ORDER BY id DESC LIMIT 10"
    ), {"t": tenant_id, "eid": employee_id})).mappings().all()
    return [dict(r) for r in rows]


async def _leave_balance(db: AsyncSession, tenant_id: int, employee_id: int) -> dict:
    types = (await db.execute(text(
        "SELECT lt.id, lt.code, lt.name, lt.days_per_year, lt.color "
        "FROM svc_leaves.leave_types lt "
        "WHERE lt.tenant_id = :t AND lt.active = true ORDER BY lt.id"
    ), {"t": tenant_id})).mappings().all()

    out: list[dict] = []
    year = date.today().year
    for lt in types:
        used = (await db.execute(text(
            "SELECT COALESCE(SUM(business_days), 0) FROM svc_leaves.leaves "
            "WHERE tenant_id = :t AND employee_id = :eid AND type_id = :tid "
            "AND status = 'approved' AND EXTRACT(year FROM start_date) = :y"
        ), {"t": tenant_id, "eid": employee_id, "tid": lt["id"], "y": year})).scalar() or 0
        out.append({
            "type_code": lt["code"], "type_name": lt["name"], "color": lt["color"],
            "annual_days": float(lt["days_per_year"] or 0),
            "used_days": float(used),
            "remaining_days": float(lt["days_per_year"] or 0) - float(used),
        })
    return {"year": year, "by_type": out}


async def _my_leaves(db: AsyncSession, tenant_id: int, employee_id: int) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT l.id, l.start_date, l.end_date, l.business_days, l.status, "
        "  lt.name AS type_name, lt.color "
        "FROM svc_leaves.leaves l "
        "LEFT JOIN svc_leaves.leave_types lt ON lt.id = l.type_id "
        "WHERE l.tenant_id = :t AND l.employee_id = :eid "
        "ORDER BY l.start_date DESC LIMIT 5"
    ), {"t": tenant_id, "eid": employee_id})).mappings().all()
    return [dict(r) for r in rows]


async def _reviews_pending(db: AsyncSession, tenant_id: int, employee_id: int) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT a.id, c.name AS cycle_name, c.period, c.deadline, "
        "  a.role, a.target_employee_id, "
        "  e.first_name, e.last_name "
        "FROM svc_reviews.review_assignments a "
        "JOIN svc_reviews.review_cycles c ON c.id = a.cycle_id "
        "LEFT JOIN svc_employees.employees e ON e.id = a.target_employee_id "
        "WHERE a.tenant_id = :t AND a.reviewer_employee_id = :eid "
        "AND a.status = 'pending' AND c.status != 'closed' "
        "ORDER BY c.deadline NULLS LAST LIMIT 8"
    ), {"t": tenant_id, "eid": employee_id})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        d["target_name"] = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or "—"
        d.pop("first_name", None); d.pop("last_name", None)
        out.append(d)
    return out


async def _my_okrs(db: AsyncSession, tenant_id: int, employee_id: int) -> list[dict]:
    rows = (await db.execute(text(
        "SELECT id, objective, scope, period, progress, status "
        "FROM svc_okrs.okrs "
        "WHERE tenant_id = :t AND owner_employee_id = :eid "
        "AND status = 'active' ORDER BY period DESC LIMIT 10"
    ), {"t": tenant_id, "eid": employee_id})).mappings().all()
    return [dict(r) for r in rows]


async def _benefits(db: AsyncSession, tenant_id: int, profile: dict) -> list[dict]:
    from services.predictions.benefits import EmployeeContext, recommend, estimate_performance_score, months_since

    kpi_rows = (await db.execute(text(
        "SELECT status, actual_value, target_value FROM svc_kpis.kpis "
        "WHERE employee_id = :id AND (tenant_id = :tid OR tenant_id IS NULL)"
    ), {"id": profile["id"], "tid": tenant_id})).all()
    perf = estimate_performance_score(
        [(str(r[0]), float(r[1] or 0), float(r[2] or 0)) for r in kpi_rows]
    )
    tenure = months_since(profile.get("hire_date"))
    ctx = EmployeeContext(
        employee_id=profile["id"],
        name=f"{profile['first_name']} {profile['last_name']}",
        department=profile.get("department"),
        position=profile.get("position"),
        salary=float(profile.get("salary") or 0),
        tenure_months=tenure,
        performance_score=perf,
    )
    recs = recommend(ctx, budget_eur=200.0, top_n=3)
    return [
        {"code": r.benefit_code, "name": r.benefit_name, "category": r.category,
         "score": r.score, "rationale": r.rationale}
        for r in recs
    ]


async def build_my_portal(db: AsyncSession, tenant_id: int, user_id: int) -> dict[str, Any]:
    profile = await _profile(db, tenant_id, user_id)
    if not profile:
        return {"error": "No tenés perfil de empleado en este tenant."}

    eid = profile["id"]
    reports     = await _safe(_reports(db, tenant_id, eid))         or []
    contracts   = await _safe(_my_contracts(db, tenant_id, eid))    or []
    leaves      = await _safe(_my_leaves(db, tenant_id, eid))       or []
    balance     = await _safe(_leave_balance(db, tenant_id, eid))   or {"year": date.today().year, "by_type": []}
    reviews     = await _safe(_reviews_pending(db, tenant_id, eid)) or []
    okrs        = await _safe(_my_okrs(db, tenant_id, eid))         or []
    benefits    = await _safe(_benefits(db, tenant_id, profile))    or []

    return {
        "profile": {
            "employee_id": eid,
            "name": f"{profile['first_name']} {profile['last_name']}",
            "position": profile.get("position"),
            "department": profile.get("department"),
            "hire_date": profile.get("hire_date"),
            "manager": (
                f"{profile.get('manager_first', '')} {profile.get('manager_last', '')}".strip()
                if profile.get("manager_id") else None
            ),
            "manager_id": profile.get("manager_id"),
        },
        "reports": reports,
        "contracts": contracts,
        "leaves": {
            "balance": balance,
            "recent": leaves,
        },
        "reviews_pending": reviews,
        "okrs": okrs,
        "benefits_recommended": benefits,
    }

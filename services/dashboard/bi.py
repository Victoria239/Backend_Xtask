"""Dashboard BI executivo (E-05 + E-06).

Agrega métricas norte cross-schema en un único endpoint:
- ARR (Annual Recurring Revenue) — suma de contratos cliente activos
- Headcount + breakdown por departamento
- Coste anual de payroll (sum salarios activos)
- P&L estimado (ARR - payroll)
- Top clientes por valor de contrato
- Distribución de riesgo de fuga (delega al motor de AI-06)
- OKRs Q actual: progreso promedio + cuántos al 100%
- Headcount trend (últimos 6 meses)
- Recent activity: contratos firmados, ausencias aprobadas

Diseño
------
Todo en queries SQL puras con joins entre schemas. Si una query falla,
devolvemos None para esa métrica en vez de romper el endpoint completo —
así el dashboard degrada elegantemente.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _safe(coro):
    """Run a coro; return None on any exception so the dashboard degrades elegantly."""
    try:
        return await coro
    except Exception:  # noqa: BLE001
        return None


async def _arr(db: AsyncSession, tenant_id: int) -> dict:
    """ARR derivado de contratos activos. Para demo asumimos valor anual en custom_fields
    o reglas simples por contract_type. Como no hay columna `amount`, hacemos una
    heurística sencilla: cada contrato activo aporta un valor fijo por tipo."""
    rows = (await db.execute(text(
        "SELECT contract_type, COUNT(*) FROM svc_contracts.contracts "
        "WHERE tenant_id = :tid AND status = 'active' AND counterparty IS NOT NULL "
        "GROUP BY contract_type"
    ), {"tid": tenant_id})).mappings().all()
    # Heurística pricing por tipo (€/año)
    PRICING = {"saas": 96000.0, "pilot": 24000.0, "labor": 0.0}
    total = sum(PRICING.get(r["contract_type"], 50000.0) * r["count"] for r in rows)
    active_clients = sum(r["count"] for r in rows if r["contract_type"] != "labor")
    return {"arr_eur": round(total), "active_clients": active_clients}


async def _headcount(db: AsyncSession, tenant_id: int) -> dict:
    rows = (await db.execute(text(
        "SELECT COALESCE(department, '— sin asignar') AS department, COUNT(*) AS n "
        "FROM svc_employees.employees WHERE tenant_id = :tid "
        "AND COALESCE(contract_status, 'active') = 'active' "
        "GROUP BY department ORDER BY n DESC"
    ), {"tid": tenant_id})).mappings().all()
    return {
        "total": sum(r["n"] for r in rows),
        "by_department": [dict(r) for r in rows],
    }


async def _payroll_cost(db: AsyncSession, tenant_id: int) -> dict:
    row = (await db.execute(text(
        "SELECT COALESCE(SUM(salary), 0) AS total, COUNT(*) AS n "
        "FROM svc_employees.employees WHERE tenant_id = :tid "
        "AND COALESCE(contract_status, 'active') = 'active' "
        "AND salary IS NOT NULL"
    ), {"tid": tenant_id})).mappings().first()
    total = float(row["total"] or 0)
    n = int(row["n"] or 0)
    return {
        "annual_eur": round(total),
        "avg_salary_eur": round(total / n) if n else 0,
    }


async def _hiring_trend(db: AsyncSession, tenant_id: int) -> list[dict]:
    """Buckets mensuales últimos 12 meses: nuevos vs total acumulado."""
    rows = (await db.execute(text(
        """
        WITH months AS (
          SELECT generate_series(
            date_trunc('month', CURRENT_DATE - INTERVAL '11 months'),
            date_trunc('month', CURRENT_DATE),
            INTERVAL '1 month'
          )::date AS m
        )
        SELECT
          m.m AS month,
          (SELECT COUNT(*) FROM svc_employees.employees
            WHERE tenant_id = :tid AND hire_date <= (m.m + INTERVAL '1 month' - INTERVAL '1 day')::date) AS headcount,
          (SELECT COUNT(*) FROM svc_employees.employees
            WHERE tenant_id = :tid AND date_trunc('month', hire_date) = m.m) AS new_hires
        FROM months m
        ORDER BY m.m
        """
    ), {"tid": tenant_id})).mappings().all()
    return [
        {"month": r["month"].isoformat(), "headcount": r["headcount"], "new_hires": r["new_hires"]}
        for r in rows
    ]


async def _okr_progress(db: AsyncSession, tenant_id: int) -> dict:
    rows = (await db.execute(text(
        "SELECT COALESCE(AVG(progress), 0) AS avg_p, COUNT(*) AS total, "
        "SUM(CASE WHEN progress >= 1.0 THEN 1 ELSE 0 END) AS completed "
        "FROM svc_okrs.okrs WHERE tenant_id = :tid AND status = 'active'"
    ), {"tid": tenant_id})).mappings().first()
    return {
        "avg_progress": round(float(rows["avg_p"] or 0), 2),
        "total": int(rows["total"] or 0),
        "completed": int(rows["completed"] or 0),
    }


async def _top_clients(db: AsyncSession, tenant_id: int) -> list[dict]:
    """Top clientes por número de contratos activos × pricing del tipo."""
    PRICING = {"saas": 96000.0, "pilot": 24000.0}
    rows = (await db.execute(text(
        "SELECT counterparty, contract_type, COUNT(*) AS n "
        "FROM svc_contracts.contracts "
        "WHERE tenant_id = :tid AND status = 'active' AND counterparty IS NOT NULL "
        "GROUP BY counterparty, contract_type"
    ), {"tid": tenant_id})).mappings().all()
    bucket: dict[str, float] = {}
    for r in rows:
        bucket[r["counterparty"]] = bucket.get(r["counterparty"], 0) + \
            PRICING.get(r["contract_type"], 50000.0) * r["n"]
    sorted_clients = sorted(bucket.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return [{"name": k, "annual_eur": round(v)} for k, v in sorted_clients]


async def _attrition_summary(db: AsyncSession, tenant_id: int) -> dict:
    """Importa el scorer y procesa todos los empleados activos.
    Es la consulta más cara — la cacheamos en memoria simple por proceso."""
    from services.predictions.attrition import score_attrition
    from services.predictions.attrition_loader import build_attrition_input as _fetch_attrition_input

    rows = (await db.execute(text(
        "SELECT id, first_name, last_name, position, department, hire_date, salary "
        "FROM svc_employees.employees WHERE tenant_id = :tid "
        "AND COALESCE(contract_status, 'active') = 'active'"
    ), {"tid": tenant_id})).all()

    bands = {"high": 0, "medium": 0, "low": 0}
    top_risks: list[dict] = []
    for row in rows:
        inp = await _fetch_attrition_input(db, tenant_id, row)
        res = score_attrition(inp)
        bands[res.risk_band] += 1
        if res.risk_band == "high":
            top_risks.append({
                "employee_id": res.employee_id,
                "name": res.employee_name,
                "score": res.risk_score,
                "department": res.department,
            })
    top_risks.sort(key=lambda r: r["score"], reverse=True)
    return {**bands, "top_risks": top_risks[:5]}


async def _pending_approvals(db: AsyncSession, tenant_id: int) -> int:
    row = (await db.execute(text(
        "SELECT COUNT(*) FROM svc_leaves.leaves "
        "WHERE tenant_id = :tid AND status = 'requested'"
    ), {"tid": tenant_id})).scalar()
    return int(row or 0)


async def build_bi_overview(db: AsyncSession, tenant_id: int) -> dict[str, Any]:
    """Punto de entrada principal — devuelve TODO el dashboard en una sola payload."""
    arr            = await _safe(_arr(db, tenant_id))           or {"arr_eur": 0, "active_clients": 0}
    headcount      = await _safe(_headcount(db, tenant_id))     or {"total": 0, "by_department": []}
    payroll        = await _safe(_payroll_cost(db, tenant_id))  or {"annual_eur": 0, "avg_salary_eur": 0}
    hiring         = await _safe(_hiring_trend(db, tenant_id))  or []
    okrs           = await _safe(_okr_progress(db, tenant_id))  or {"avg_progress": 0, "total": 0, "completed": 0}
    clients        = await _safe(_top_clients(db, tenant_id))   or []
    attrition      = await _safe(_attrition_summary(db, tenant_id)) or {"high": 0, "medium": 0, "low": 0, "top_risks": []}
    pending_apps   = await _safe(_pending_approvals(db, tenant_id)) or 0

    # Derivadas
    pnl = arr["arr_eur"] - payroll["annual_eur"]
    runway_months = round((arr["arr_eur"] / payroll["annual_eur"]) * 12, 1) if payroll["annual_eur"] else 0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "north_star": {
            "arr_eur": arr["arr_eur"],
            "headcount": headcount["total"],
            "active_clients": arr["active_clients"],
            "okr_avg_progress": okrs["avg_progress"],
        },
        "financial": {
            "arr_eur": arr["arr_eur"],
            "payroll_annual_eur": payroll["annual_eur"],
            "avg_salary_eur": payroll["avg_salary_eur"],
            "pnl_annual_eur": pnl,
            "runway_implied_months": runway_months,
        },
        "people": {
            "headcount_total": headcount["total"],
            "headcount_by_department": headcount["by_department"],
            "hiring_trend": hiring,
            "pending_leave_approvals": pending_apps,
            "attrition": attrition,
        },
        "performance": {
            "okrs": okrs,
        },
        "revenue": {
            "top_clients": clients,
        },
    }

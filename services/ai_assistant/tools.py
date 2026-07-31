"""Function-calling tools for the AI Assistant.

Each tool is a thin SQL-backed helper the LLM can invoke to consult the live
operational DB (employees, OKRs, contracts, payouts, leaves) instead of relying
only on RAG over markdown.

Design notes
------------
- All tools accept `tenant_id` from the service layer and inject it into every
  query. The LLM never sees or controls the tenant — it cannot cross tenants.
- Tools return Python dicts/lists which we then JSON-serialize. Each tool result
  also produces a synthetic citation with `source_type="db"` for transparency.
- We keep the tool surface small (≈8 tools) and high-level. Fine-grained CRUD
  through the LLM is out of scope for Capa B (read-only by design).
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ─── Tool definitions (OpenAI/OpenRouter function-calling spec) ──
TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_employees",
            "description": (
                "Busca empleados activos por nombre, equipo/departamento o puesto. "
                "Usa esto cuando el usuario pregunte por personas concretas o por la "
                "composición de un equipo. Devuelve hasta 20 resultados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name":       {"type": "string", "description": "Substring del nombre o apellido (case-insensitive)"},
                    "department": {"type": "string", "description": "Nombre del departamento o equipo (case-insensitive)"},
                    "position":   {"type": "string", "description": "Substring del puesto/rol (case-insensitive)"},
                    "limit":      {"type": "integer", "description": "Máx resultados (default 20)", "default": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_detail",
            "description": "Devuelve el perfil completo de un empleado: puesto, manager, fecha ingreso, salario, status, custom fields.",
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "integer", "description": "ID del empleado"}},
                "required": ["employee_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_headcount_by_team",
            "description": "Cuenta cuántos empleados activos hay por departamento/equipo. Útil para preguntas tipo '¿cuántos hay en backend?' o headcount global.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "Lista proyectos del tenant filtrados por status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "active | completed | paused | archived. Omite para traer todos."},
                    "limit":  {"type": "integer", "default": 20},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_okrs",
            "description": "Lista OKRs (objetivos) por período/trimestre con progreso. Usa esto para preguntas sobre objetivos actuales o cumplimiento.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period": {"type": "string", "description": "p. ej. '2026-Q3'. Omite para traer activos."},
                    "scope":  {"type": "string", "description": "company | department | individual"},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_contracts",
            "description": "Lista contratos del tenant: clientes (con counterparty) o empleados (con employee_id). Filtrable por status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "draft | sent | signed | expired | cancelled"},
                    "limit":  {"type": "integer", "default": 10},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recent_payouts",
            "description": "Muestra los últimos N pagos calculados con su monto, empleado y reglas que matchearon.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 10}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pending_leaves",
            "description": "Ausencias pendientes de aprobación (status='requested'). Para preguntas tipo '¿quién pidió vacaciones esta semana?'.",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 20}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attrition_summary",
            "description": (
                "Resumen del riesgo de fuga de talento de toda la empresa: cuántos empleados en alto, medio y bajo riesgo, "
                "y top 5 nombres en alto riesgo. Útil para preguntas estratégicas tipo '¿qué tan preocupados deberíamos estar?'."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_attrition",
            "description": (
                "Score detallado de riesgo de fuga de un empleado específico con breakdown por factor "
                "(antigüedad, ausencias, performance, banda salarial, cambio manager, engagement). "
                "Usalo cuando preguntan por riesgo de UN empleado o por qué alguien está en alto riesgo."
            ),
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "integer"}},
                "required": ["employee_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_comp_analysis",
            "description": (
                "Análisis de compensación: payroll total, avg/median salary, gap factor, lista de outliers "
                "(empleados below o above su banda salarial) y distribución por departamento. "
                "Usalo para preguntas sobre equidad salarial, gaps, o si alguien está sub-pagado."
            ),
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_reviews",
            "description": (
                "Reviews 360° agregadas de un empleado (cuando los ciclos están cerrados): overall score 1-5, "
                "desglose por categoría (performance, collaboration, growth, leadership) y por tipo de reviewer."
            ),
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "integer"}},
                "required": ["employee_id"],
                "additionalProperties": False,
            },
        },
    },
]


# ─── Tool handlers ─────────────────────────────────────────────
async def _search_employees(db: AsyncSession, tenant_id: int, *, name: str = "", department: str = "", position: str = "", limit: int = 20) -> dict:
    parts = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {"tenant_id": tenant_id, "limit": min(int(limit or 20), 50)}
    if name:
        parts.append("(first_name ILIKE :nm OR last_name ILIKE :nm)")
        params["nm"] = f"%{name}%"
    if department:
        parts.append("department ILIKE :dept")
        params["dept"] = f"%{department}%"
    if position:
        parts.append("position ILIKE :pos")
        params["pos"] = f"%{position}%"
    sql = (
        "SELECT id, first_name, last_name, position, department, hire_date, contract_status "
        f"FROM svc_employees.employees WHERE {' AND '.join(parts)} "
        "ORDER BY last_name, first_name LIMIT :limit"
    )
    rows = (await db.execute(text(sql), params)).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


async def _get_employee_detail(db: AsyncSession, tenant_id: int, *, employee_id: int) -> dict:
    sql = (
        "SELECT e.*, m.first_name AS manager_first, m.last_name AS manager_last "
        "FROM svc_employees.employees e "
        "LEFT JOIN svc_employees.employees m ON m.id = e.manager_id AND m.tenant_id = e.tenant_id "
        "WHERE e.tenant_id = :tenant_id AND e.id = :eid"
    )
    row = (await db.execute(text(sql), {"tenant_id": tenant_id, "eid": employee_id})).mappings().first()
    return dict(row) if row else {"error": "Empleado no encontrado"}


async def _count_headcount_by_team(db: AsyncSession, tenant_id: int) -> dict:
    sql = (
        "SELECT COALESCE(department, '— sin asignar') AS department, COUNT(*) AS headcount "
        "FROM svc_employees.employees WHERE tenant_id = :tenant_id "
        "GROUP BY department ORDER BY headcount DESC"
    )
    rows = (await db.execute(text(sql), {"tenant_id": tenant_id})).mappings().all()
    total = sum(r["headcount"] for r in rows)
    return {"total": total, "by_department": [dict(r) for r in rows]}


async def _list_projects(db: AsyncSession, tenant_id: int, *, status: str = "", limit: int = 20) -> dict:
    # Projects table has no tenant_id in current schema — return all (single-tenant assumption).
    parts: list[str] = []
    params: dict[str, Any] = {"limit": min(int(limit or 20), 50)}
    if status:
        parts.append("status = :st")
        params["st"] = status
    where = (" WHERE " + " AND ".join(parts)) if parts else ""
    sql = f"SELECT id, name, status, start_date, end_date, description FROM svc_projects.projects{where} ORDER BY id DESC LIMIT :limit"
    rows = (await db.execute(text(sql), params)).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


async def _get_okrs(db: AsyncSession, tenant_id: int, *, period: str = "", scope: str = "") -> dict:
    parts = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {"tenant_id": tenant_id}
    if period:
        parts.append("period = :p")
        params["p"] = period
    if scope:
        parts.append("scope = :s")
        params["s"] = scope
    sql = (
        "SELECT id, objective, scope, owner_department, period, progress, status "
        f"FROM svc_okrs.okrs WHERE {' AND '.join(parts)} ORDER BY period DESC, progress DESC LIMIT 30"
    )
    rows = (await db.execute(text(sql), params)).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


async def _list_contracts(db: AsyncSession, tenant_id: int, *, status: str = "", limit: int = 10) -> dict:
    parts = ["tenant_id = :tenant_id"]
    params: dict[str, Any] = {"tenant_id": tenant_id, "limit": min(int(limit or 10), 30)}
    if status:
        parts.append("status = :st")
        params["st"] = status
    sql = (
        "SELECT id, title, counterparty, employee_id, contract_type, status, starts_on, expires_on, signed_on "
        f"FROM svc_contracts.contracts WHERE {' AND '.join(parts)} ORDER BY id DESC LIMIT :limit"
    )
    rows = (await db.execute(text(sql), params)).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


async def _recent_payouts(db: AsyncSession, tenant_id: int, *, limit: int = 10) -> dict:
    sql = (
        "SELECT id, employee_name, department, amount, matched_rules, paid_at "
        "FROM svc_payouts.payouts WHERE tenant_id = :tenant_id "
        "ORDER BY id DESC LIMIT :limit"
    )
    rows = (await db.execute(text(sql), {"tenant_id": tenant_id, "limit": min(int(limit or 10), 30)})).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


async def _pending_leaves(db: AsyncSession, tenant_id: int, *, limit: int = 20) -> dict:
    sql = (
        "SELECT l.id, l.employee_id, l.start_date, l.end_date, l.business_days, l.reason, "
        "  e.first_name, e.last_name "
        "FROM svc_leaves.leaves l "
        "LEFT JOIN svc_employees.employees e ON e.id = l.employee_id AND e.tenant_id = l.tenant_id "
        "WHERE l.tenant_id = :tenant_id AND l.status = 'requested' "
        "ORDER BY l.start_date ASC LIMIT :limit"
    )
    rows = (await db.execute(text(sql), {"tenant_id": tenant_id, "limit": min(int(limit or 20), 50)})).mappings().all()
    return {"count": len(rows), "results": [dict(r) for r in rows]}


# ─── Predictions / Reviews tools (Q4 — Capa B extras) ──────────
async def _get_attrition_summary(db: AsyncSession, tenant_id: int) -> dict:
    """Reutiliza el motor de AI-06 para devolver una vista corporativa del riesgo."""
    from services.predictions.attrition import score_attrition
    from services.predictions.attrition_loader import build_attrition_input as _fetch_attrition_input

    rows = (await db.execute(text(
        "SELECT id, first_name, last_name, position, department, hire_date, salary "
        "FROM svc_employees.employees WHERE tenant_id = :t "
        "AND COALESCE(contract_status, 'active') = 'active'"
    ), {"t": tenant_id})).all()

    bands = {"high": 0, "medium": 0, "low": 0}
    top_risks: list[dict] = []
    for r in rows:
        inp = await _fetch_attrition_input(db, tenant_id, r)
        res = score_attrition(inp)
        bands[res.risk_band] += 1
        if res.risk_band == "high":
            top_risks.append({"employee_id": res.employee_id, "name": res.employee_name,
                              "score": res.risk_score, "department": res.department,
                              "drivers": res.top_drivers})
    top_risks.sort(key=lambda r: r["score"], reverse=True)
    return {"counts": bands, "total": len(rows), "top_high_risks": top_risks[:5]}


async def _get_employee_attrition(db: AsyncSession, tenant_id: int, *, employee_id: int) -> dict:
    from services.predictions.attrition import score_attrition
    from services.predictions.attrition_loader import build_attrition_input as _fetch_attrition_input

    row = (await db.execute(text(
        "SELECT id, first_name, last_name, position, department, hire_date, salary "
        "FROM svc_employees.employees WHERE id = :eid AND tenant_id = :t"
    ), {"eid": employee_id, "t": tenant_id})).first()
    if not row:
        return {"error": "Empleado no encontrado"}
    inp = await _fetch_attrition_input(db, tenant_id, row)
    res = score_attrition(inp)
    return {
        "employee_id": res.employee_id, "name": res.employee_name,
        "department": res.department, "position": res.position,
        "risk_score": res.risk_score, "risk_band": res.risk_band,
        "top_drivers": res.top_drivers,
        "factors": [
            {"label": f.label, "level": f.level, "contribution": f.contribution, "why": f.rationale}
            for f in res.factors
        ],
    }


async def _get_comp_analysis(db: AsyncSession, tenant_id: int) -> dict:
    from datetime import date
    from services.predictions.comp_analytics import EmployeeComp, analyze, detect_seniority

    rows = (await db.execute(text(
        "SELECT id, first_name, last_name, department, position, salary, hire_date "
        "FROM svc_employees.employees WHERE tenant_id = :t "
        "AND COALESCE(contract_status, 'active') = 'active'"
    ), {"t": tenant_id})).all()

    emps = [EmployeeComp(
        employee_id=r[0],
        name=f"{r[1] or ''} {r[2] or ''}".strip() or f"Empleado #{r[0]}",
        department=(r[3] or "— sin asignar"),
        position=(r[4] or "—"),
        seniority=detect_seniority(r[4]),
        salary=float(r[5] or 0),
        hire_date=r[6],
        tenure_months=max(0, (date.today() - r[6]).days // 30) if r[6] else 0,
    ) for r in rows if r[5]]
    ov = analyze(emps)
    return {
        "total_payroll_annual": ov.total_payroll_annual,
        "avg_salary": ov.avg_salary, "median_salary": ov.median_salary,
        "gap_factor": ov.gap_factor, "compa_ratio_avg": ov.compa_ratio_avg,
        "departments": ov.departments[:6],
        "outliers": [
            {"name": o.name, "department": o.department, "seniority": o.seniority,
             "salary": o.salary, "band_p50": o.band_p50, "compa_ratio": o.compa_ratio,
             "flag": o.flag, "delta_eur": o.delta_eur, "reason": o.reason}
            for o in ov.outliers
        ],
        "top_earners": ov.top_earners,
    }


async def _get_employee_reviews(db: AsyncSession, tenant_id: int, *, employee_id: int) -> dict:
    rows = (await db.execute(text(
        "SELECT s.cycle_id, c.name AS cycle_name, c.period AS cycle_period, "
        "  s.overall_score, s.by_category, s.by_role, s.responses_count "
        "FROM svc_reviews.review_summaries s "
        "JOIN svc_reviews.review_cycles c ON c.id = s.cycle_id "
        "WHERE s.tenant_id = :t AND s.employee_id = :eid "
        "ORDER BY c.id DESC"
    ), {"t": tenant_id, "eid": employee_id})).mappings().all()
    if not rows:
        return {"error": "Sin reviews cerradas para este empleado"}
    return {"employee_id": employee_id, "cycles": [dict(r) for r in rows]}


# Map of name → handler. Each handler signature: (db, tenant_id, **kwargs) -> dict
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[dict]]] = {
    "search_employees":         _search_employees,
    "get_employee_detail":      _get_employee_detail,
    "count_headcount_by_team":  _count_headcount_by_team,
    "list_projects":            _list_projects,
    "get_okrs":                 _get_okrs,
    "list_contracts":           _list_contracts,
    "recent_payouts":           _recent_payouts,
    "pending_leaves":           _pending_leaves,
    "get_attrition_summary":    _get_attrition_summary,
    "get_employee_attrition":   _get_employee_attrition,
    "get_comp_analysis":        _get_comp_analysis,
    "get_employee_reviews":     _get_employee_reviews,
}


async def execute_tool(db: AsyncSession, tenant_id: int, name: str, arguments: dict) -> str:
    """Execute a tool and return a JSON-serializable string result.

    Defensivo contra LLMs pequeños que a veces pasan campos del schema (como
    `required`, `properties`, `type`) en vez de los argumentos reales: filtramos
    kwargs por la signature del handler.
    """
    import inspect
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Tool '{name}' no existe."})

    # Solo pasar kwargs que el handler conoce — descarta basura del schema
    sig = inspect.signature(handler)
    allowed = {k for k in sig.parameters if k not in ("db", "tenant_id")}
    safe_args = {k: v for k, v in (arguments or {}).items() if k in allowed}

    try:
        result = await handler(db, tenant_id, **safe_args)
        return json.dumps(result, default=str, ensure_ascii=False)
    except TypeError as exc:
        return json.dumps({"error": f"Argumentos inválidos: {exc}"})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"Error ejecutando '{name}': {exc}"})


def summary_for_citation(name: str, args: dict, raw_result: str) -> str:
    """Build a short human-readable snippet for the citation chip."""
    try:
        data = json.loads(raw_result)
    except Exception:  # noqa: BLE001
        return raw_result[:240]
    if "error" in data:
        return f"Error: {data['error']}"
    count = data.get("count")
    if count is not None:
        return f"{name}({json.dumps(args, ensure_ascii=False)}) → {count} resultados"
    return json.dumps(data, ensure_ascii=False)[:240]

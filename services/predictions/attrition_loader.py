"""Construye los EmployeeAttritionInput desde la DB.

Extraído de predictions/router.py (Q5 audit C1) para que el BI dashboard,
los AI tools y el portal puedan reusarlo sin importar del router.

Mantener este módulo PURE — solo SELECT statements, sin escritura.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.predictions.attrition import EmployeeAttritionInput
from services.predictions.benefits import estimate_performance_score


# Tupla esperada en emp_row (orden importa):
# (id, first_name, last_name, position, department, hire_date, salary)
EXPECTED_COLS = "id, first_name, last_name, position, department, hire_date, salary"


def employees_select_sql() -> str:
    """SELECT estándar de empleados activos para attrition.

    Útil para callers que quieran construir su query base y luego pasarla
    fila por fila a `build_attrition_input()`.
    """
    return (
        f"SELECT {EXPECTED_COLS} "
        "FROM svc_employees.employees "
        "WHERE tenant_id = :tid "
        "AND COALESCE(contract_status, 'active') = 'active'"
    )


async def build_attrition_input(
    db: AsyncSession, tenant_id: int, emp_row
) -> EmployeeAttritionInput:
    """Construye el input desde la DB con joins a kpis, leaves, okrs.

    Args:
        db: sesión SQLAlchemy async.
        tenant_id: tenant en cuyo contexto se evalúa.
        emp_row: tupla `(id, first_name, last_name, position, department, hire_date, salary)`.

    Returns:
        EmployeeAttritionInput listo para `score_attrition()`.
    """
    emp_id = emp_row[0]

    # Ausencias últimos 6 meses
    leaves_n = (await db.execute(
        text(
            "SELECT COUNT(*) FROM svc_leaves.leaves "
            "WHERE tenant_id = :tid AND employee_id = :eid "
            "AND start_date >= (CURRENT_DATE - INTERVAL '6 months')"
        ),
        {"tid": tenant_id, "eid": emp_id},
    )).scalar() or 0

    # Performance via KPIs
    kpi_rows = (await db.execute(
        text(
            "SELECT status, actual_value, target_value FROM svc_kpis.kpis "
            "WHERE employee_id = :eid AND (tenant_id = :tid OR tenant_id IS NULL)"
        ),
        {"tid": tenant_id, "eid": emp_id},
    )).all()
    perf = estimate_performance_score(
        [(str(r[0]), float(r[1] or 0), float(r[2] or 0)) for r in kpi_rows]
    )

    # OKRs
    okr_rows = (await db.execute(
        text(
            "SELECT progress FROM svc_okrs.okrs "
            "WHERE tenant_id = :tid AND owner_employee_id = :eid"
        ),
        {"tid": tenant_id, "eid": emp_id},
    )).all()
    okrs_n = len(okr_rows)
    okrs_progress = (sum(float(r[0] or 0) for r in okr_rows) / okrs_n) if okrs_n else 0.0

    # Manager change (heurística: updated en últimos 6m con manager_id)
    mgr_changed = bool((await db.execute(
        text(
            "SELECT 1 FROM svc_employees.employees "
            "WHERE id = :eid AND tenant_id = :tid AND manager_id IS NOT NULL "
            "AND updated_at >= (CURRENT_DATE - INTERVAL '6 months') "
            "AND updated_at != created_at"
        ),
        {"tid": tenant_id, "eid": emp_id},
    )).first())

    # Avg salary del departamento
    dept_avg = (await db.execute(
        text(
            "SELECT AVG(salary) FROM svc_employees.employees "
            "WHERE tenant_id = :tid AND department = :dept AND salary IS NOT NULL"
        ),
        {"tid": tenant_id, "dept": emp_row[4]},
    )).scalar() or 0.0

    return EmployeeAttritionInput(
        employee_id=emp_id,
        name=f"{emp_row[1]} {emp_row[2]}",
        department=emp_row[4],
        position=emp_row[3],
        hire_date=emp_row[5],
        salary=float(emp_row[6] or 0),
        leaves_last_6m=int(leaves_n),
        avg_kpi_score=perf,
        okrs_assigned=okrs_n,
        okrs_avg_progress=okrs_progress,
        manager_changed_within_6m=mgr_changed,
        department_avg_salary=float(dept_avg),
    )

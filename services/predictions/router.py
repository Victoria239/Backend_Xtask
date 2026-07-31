"""Predictions service — HTTP routes (AI-04 + AI-05 + AI-06 + C-06)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_service_db
from shared.dependencies import get_current_tenant_id
from services.predictions.benefits import (
    EmployeeContext, Recommendation, estimate_performance_score, months_since, recommend,
)
from services.predictions.attrition import EmployeeAttritionInput, score_attrition
from services.predictions.attrition_loader import build_attrition_input
from services.predictions.comp_analytics import (
    EmployeeComp, analyze as analyze_comp, detect_seniority,
)
from services.predictions.people_analytics import PersonRow, analyze_people
from services.predictions.forecasting import ForecastPoint, forecast_series
from services.predictions.schemas import (
    AttritionFactorOut, AttritionListResponse, AttritionResultOut,
    CompBandOut, CompOutlierOut, CompOverviewOut,
    NineBoxCellOut, PeopleOverviewOut,
    ForecastPointOut, ForecastResponse,
)

router = APIRouter()


def _to_point(p: ForecastPoint) -> ForecastPointOut:
    return ForecastPointOut(t=p.t, value=p.value, ic_low=p.ic_low, ic_high=p.ic_high)


# ─── AI-05 Recomendación beneficios ─────────────────────────
class BenefitRecommendation(BaseModel):
    benefit_code: str
    benefit_name: str
    category: str
    monthly_cost_eur: float
    score: float
    rationale: str


class RecommendResponse(BaseModel):
    employee_id: int
    employee_name: str
    tenure_months: int
    performance_score: float
    budget_eur: float
    recommendations: list[BenefitRecommendation]


@router.get("/benefits/employee/{employee_id}", response_model=RecommendResponse)
async def recommend_benefits(
    employee_id: int,
    budget_eur: float = Query(200.0, ge=0, le=10000, description="Presupuesto mensual disponible"),
    top_n: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    # 1) Empleado
    emp_row = (await db.execute(
        text(
            "SELECT first_name || ' ' || last_name, department, position, salary, created_at "
            "FROM svc_employees.employees WHERE id = :id AND tenant_id = :tid LIMIT 1"
        ),
        {"id": employee_id, "tid": tenant_id},
    )).first()
    if not emp_row:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    tenure = months_since(emp_row[4])

    # 2) KPIs del empleado para performance
    kpi_rows = (await db.execute(
        text(
            "SELECT status, actual_value, target_value FROM svc_kpis.kpis "
            "WHERE employee_id = :id AND (tenant_id = :tid OR tenant_id IS NULL)"
        ),
        {"id": employee_id, "tid": tenant_id},
    )).all()
    perf = estimate_performance_score([(str(r[0]), float(r[1] or 0), float(r[2] or 0)) for r in kpi_rows])

    ctx = EmployeeContext(
        employee_id=employee_id,
        name=str(emp_row[0]),
        department=emp_row[1],
        position=emp_row[2],
        salary=float(emp_row[3] or 0),
        tenure_months=tenure,
        performance_score=perf,
    )
    recs = recommend(ctx, budget_eur=budget_eur, top_n=top_n)

    return RecommendResponse(
        employee_id=employee_id,
        employee_name=ctx.name,
        tenure_months=tenure,
        performance_score=perf,
        budget_eur=budget_eur,
        recommendations=[
            BenefitRecommendation(
                benefit_code=r.benefit_code, benefit_name=r.benefit_name,
                category=r.category, monthly_cost_eur=r.monthly_cost_eur,
                score=r.score, rationale=r.rationale,
            )
            for r in recs
        ],
    )


@router.get("/benefits/catalog")
async def benefits_catalog():
    """Devuelve el catálogo completo para mostrar en UI."""
    from services.predictions.benefits import CATALOG
    return [
        {
            "code": b.code, "name": b.name, "category": b.category,
            "monthly_cost_eur": b.monthly_cost_eur, "description": b.description,
            "min_tenure_months": b.min_tenure_months, "min_performance": b.min_performance,
        }
        for b in CATALOG
    ]


@router.get("/kpi/{kpi_id}/forecast", response_model=ForecastResponse)
async def forecast_kpi(
    kpi_id: int,
    horizon: int = Query(6, ge=1, le=24, description="Períodos futuros a predecir"),
    freq_days: float = Query(30.0, ge=1, le=365, description="Días entre puntos del forecast"),
    method: str | None = Query(None, description="linear | holt | naive (None = auto)"),
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    # 1) Leer KPI
    kpi_row = (await db.execute(
        text(
            "SELECT name, target_value FROM svc_kpis.kpis "
            "WHERE id = :id AND (tenant_id = :tid OR tenant_id IS NULL) LIMIT 1"
        ),
        {"id": kpi_id, "tid": tenant_id},
    )).first()
    if not kpi_row:
        raise HTTPException(status_code=404, detail="KPI no encontrado")
    kpi_name = str(kpi_row[0])
    target = float(kpi_row[1]) if kpi_row[1] is not None else None

    # 2) Leer mediciones
    rows = (await db.execute(
        text(
            "SELECT recorded_at, value FROM svc_kpis.kpi_measurements "
            "WHERE kpi_id = :id AND (tenant_id = :tid OR tenant_id IS NULL) "
            "ORDER BY recorded_at ASC"
        ),
        {"id": kpi_id, "tid": tenant_id},
    )).all()

    timestamps = [r[0] for r in rows]
    values = [float(r[1]) for r in rows]

    # 3) Calcular forecast
    try:
        result = forecast_series(
            timestamps, values, horizon=horizon, freq_days=freq_days,
            method=method,  # type: ignore[arg-type]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # 4) Historia como FP para que el frontend la dibuje con el mismo schema
    history = [
        ForecastPointOut(t=t, value=v, ic_low=v, ic_high=v) for t, v in zip(timestamps, values)
    ]

    return ForecastResponse(
        kpi_id=kpi_id, kpi_name=kpi_name,
        horizon=horizon, freq_days=freq_days,
        method=result.method, r2=result.r2,
        last_observed_at=result.last_observed_at,
        last_observed_value=result.last_observed_value,
        target=target,
        forecast=[_to_point(p) for p in result.points],
        history=history,
    )


# ─── AI-06 Predicción fuga de talento ───────────────────────────
# Lógica de carga movida a attrition_loader.py (Q5 audit C1).
# Mantenemos este alias para compat con tests existentes.
_fetch_attrition_input = build_attrition_input


@router.get("/attrition/all", response_model=AttritionListResponse)
async def attrition_all(
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Ranking de riesgo de churn de todos los empleados activos del tenant."""
    from datetime import datetime, timezone

    emp_rows = (await db.execute(
        text(
            "SELECT id, first_name, last_name, position, department, hire_date, salary "
            "FROM svc_employees.employees "
            "WHERE tenant_id = :tid AND COALESCE(contract_status, 'active') = 'active' "
            "ORDER BY last_name, first_name"
        ),
        {"tid": tenant_id},
    )).all()

    results: list[AttritionResultOut] = []
    by_dept: dict[str, int] = {}
    high = med = low = 0
    for row in emp_rows:
        inp = await _fetch_attrition_input(db, tenant_id, row)
        res = score_attrition(inp)
        dept = res.department or "— sin asignar"
        if res.risk_band == "high":
            high += 1
            by_dept[dept] = by_dept.get(dept, 0) + 1
        elif res.risk_band == "medium":
            med += 1
        else:
            low += 1
        results.append(AttritionResultOut(
            employee_id=res.employee_id,
            employee_name=res.employee_name,
            department=res.department,
            position=res.position,
            risk_score=res.risk_score,
            risk_band=res.risk_band,
            factors=[AttritionFactorOut(**vars(f)) for f in res.factors],
            top_drivers=res.top_drivers,
        ))

    results.sort(key=lambda r: r.risk_score, reverse=True)
    return AttritionListResponse(
        generated_at=datetime.now(timezone.utc),
        total_employees=len(results),
        high_risk=high, medium_risk=med, low_risk=low,
        by_department=by_dept,
        employees=results,
    )


@router.get("/attrition/employee/{employee_id}", response_model=AttritionResultOut)
async def attrition_employee(
    employee_id: int,
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Risk score detallado con breakdown de un empleado."""
    emp_row = (await db.execute(
        text(
            "SELECT id, first_name, last_name, position, department, hire_date, salary "
            "FROM svc_employees.employees WHERE id = :eid AND tenant_id = :tid"
        ),
        {"eid": employee_id, "tid": tenant_id},
    )).first()
    if not emp_row:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    inp = await _fetch_attrition_input(db, tenant_id, emp_row)
    res = score_attrition(inp)
    return AttritionResultOut(
        employee_id=res.employee_id,
        employee_name=res.employee_name,
        department=res.department,
        position=res.position,
        risk_score=res.risk_score,
        risk_band=res.risk_band,
        factors=[AttritionFactorOut(**vars(f)) for f in res.factors],
        top_drivers=res.top_drivers,
    )


# ─── C-06 Comp analytics ─────────────────────────────────────────
@router.get("/comp/overview", response_model=CompOverviewOut)
async def comp_overview(
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Compensation analytics: bandas, outliers, distribución por depto."""
    rows = (await db.execute(text(
        "SELECT id, first_name, last_name, department, position, salary, hire_date "
        "FROM svc_employees.employees "
        "WHERE tenant_id = :tid AND COALESCE(contract_status, 'active') = 'active'"
    ), {"tid": tenant_id})).all()

    employees: list[EmployeeComp] = []
    for r in rows:
        if not r[5]:
            continue
        name = f"{r[1]} {r[2]}".strip() or f"Empleado #{r[0]}"
        position = r[4] or "—"
        employees.append(EmployeeComp(
            employee_id=r[0],
            name=name,
            department=(r[3] or "— sin asignar"),
            position=position,
            seniority=detect_seniority(position),
            salary=float(r[5] or 0),
            hire_date=r[6],
            tenure_months=max(0, (datetime.now().date() - r[6]).days // 30) if r[6] else 0,
        ))

    overview = analyze_comp(employees)
    return CompOverviewOut(
        total_employees=overview.total_employees,
        total_payroll_annual=overview.total_payroll_annual,
        avg_salary=overview.avg_salary,
        median_salary=overview.median_salary,
        gap_factor=overview.gap_factor,
        compa_ratio_avg=overview.compa_ratio_avg,
        departments=overview.departments,
        bands=[CompBandOut(**vars(b)) for b in overview.bands],
        outliers=[CompOutlierOut(**vars(o)) for o in overview.outliers],
        top_earners=overview.top_earners,
        tenure_vs_salary=overview.tenure_vs_salary,
    )


# ─── H-07 People Analytics ──────────────────────────────────────
@router.get("/people/overview", response_model=PeopleOverviewOut)
async def people_overview(
    db: AsyncSession = Depends(get_service_db("predictions")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Dashboard de talento: tenure, 9-box, span of control, segment risk, diversity."""
    emp_rows = (await db.execute(
        text(
            "SELECT id, first_name, last_name, position, department, hire_date, salary, manager_id "
            "FROM svc_employees.employees "
            "WHERE tenant_id = :tid AND COALESCE(contract_status, 'active') = 'active'"
        ),
        {"tid": tenant_id},
    )).all()

    rows: list[PersonRow] = []
    for r in emp_rows:
        if not r[5]:  # sin hire_date no podemos calcular tenure
            continue
        # Reusar attrition loader para performance + score (consistencia con AI-06)
        attr_input = await build_attrition_input(db, tenant_id, (
            r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        ))
        attr = score_attrition(attr_input)
        rows.append(PersonRow(
            employee_id=r[0],
            name=f"{r[1]} {r[2]}".strip() or f"Empleado #{r[0]}",
            department=(r[4] or "— sin asignar"),
            position=(r[3] or "—"),
            seniority=detect_seniority(r[3]),
            salary=float(r[6] or 0),
            tenure_months=max(0, (datetime.now().date() - r[5]).days // 30),
            manager_id=r[7],
            performance=attr_input.avg_kpi_score,
            attrition_score=attr.risk_score,
            attrition_band=attr.risk_band,
        ))

    ov = analyze_people(rows)
    return PeopleOverviewOut(
        total_employees=ov.total_employees,
        avg_tenure_months=ov.avg_tenure_months,
        avg_performance=ov.avg_performance,
        managers_count=ov.managers_count,
        tenure_distribution=ov.tenure_distribution,
        span_of_control=ov.span_of_control,
        nine_box=[NineBoxCellOut(**vars(c)) for c in ov.nine_box],
        segment_risk=ov.segment_risk,
        diversity=ov.diversity,
        band_saturation=ov.band_saturation,
    )

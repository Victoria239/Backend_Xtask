"""Motor de predicción de fuga de talento (AI-06).

Cómo funciona
-------------
No usamos ML supervisado porque no tenemos labels históricos. En su lugar,
un scoring rule-based con factores ponderados que reflejan los drivers
empíricos de churn más documentados en la literatura HR:

| Factor          | Peso | Señal                                       |
|-----------------|------|---------------------------------------------|
| Tenure          | 25%  | Riesgo U-shape: <6m (mismatch) y >60m (vested) |
| Leave freq      | 20%  | Burnout — alta frecuencia de ausencias 6m   |
| Performance     | 20%  | Bajo desempeño correlaciona con salida      |
| Salary band     | 15%  | Pago por debajo del rango = riesgo          |
| Manager change  | 10%  | Cambio reciente de manager                  |
| Engagement      | 10%  | OKRs sin progreso, sin objetivos asignados  |

Cada factor produce un valor [0..1] (su `level` de riesgo). El score final
es la suma ponderada × 100, redondeado. El response trae el breakdown
completo para que RH pueda explicar la sugerencia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


# ─── Inputs ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class EmployeeAttritionInput:
    employee_id: int
    name: str
    department: str | None
    position: str | None
    hire_date: date | None
    salary: float
    leaves_last_6m: int
    avg_kpi_score: float        # 0..1 — 1=mejor
    okrs_assigned: int
    okrs_avg_progress: float    # 0..1 — 1=completo
    manager_changed_within_6m: bool
    department_avg_salary: float


# ─── Outputs ────────────────────────────────────────────────────
@dataclass
class AttritionFactor:
    code: str
    label: str
    level: float          # 0..1, contribución de riesgo bruta de este factor
    weight: float         # peso normalizado (0..1)
    contribution: float   # level * weight * 100
    rationale: str


@dataclass
class AttritionResult:
    employee_id: int
    employee_name: str
    department: str | None
    position: str | None
    risk_score: int        # 0..100
    risk_band: str         # low | medium | high
    factors: list[AttritionFactor] = field(default_factory=list)
    top_drivers: list[str] = field(default_factory=list)


# ─── Pesos ──────────────────────────────────────────────────────
WEIGHTS = {
    "tenure":          0.25,
    "leave_freq":      0.20,
    "performance":     0.20,
    "salary_band":     0.15,
    "manager_change":  0.10,
    "engagement":      0.10,
}


def _band(score: int) -> str:
    """Umbrales calibrados con literatura HR: >50 acción inmediata, 25-50 vigilar."""
    if score >= 50:
        return "high"
    if score >= 25:
        return "medium"
    return "low"


def _tenure_risk(hire_date: date | None) -> tuple[float, str]:
    """U-shape: alto riesgo en 0-6m y 60+m, bajo en 12-48m."""
    if not hire_date:
        return 0.5, "Sin fecha de ingreso — riesgo medio por defecto"
    months = max(0, (date.today() - hire_date).days // 30)
    if months < 6:
        return 0.7, f"Solo {months}m en la empresa (período de adaptación)"
    if months < 12:
        return 0.5, f"{months}m de antigüedad (todavía estabilizándose)"
    if months <= 48:
        return 0.15, f"{months}m — zona estable de retención"
    if months <= 72:
        return 0.55, f"{months}m — vested, riesgo de buscar nuevo desafío"
    return 0.75, f"{months}m — alto riesgo de búsqueda externa"


def _leave_risk(n_leaves: int) -> tuple[float, str]:
    """Más de 4 ausencias en 6m sugiere burnout o desenganche."""
    if n_leaves >= 6:
        return 0.85, f"{n_leaves} ausencias en 6m — señal fuerte de burnout"
    if n_leaves >= 4:
        return 0.6, f"{n_leaves} ausencias en 6m — patrón a vigilar"
    if n_leaves >= 2:
        return 0.3, f"{n_leaves} ausencias en 6m — uso normal"
    return 0.1, f"{n_leaves} ausencias en 6m — uso bajo"


def _performance_risk(score: float) -> tuple[float, str]:
    """Bajo desempeño = mayor riesgo de salida."""
    if score < 0.3:
        return 0.8, f"Performance {int(score*100)}% — desempeño muy bajo"
    if score < 0.5:
        return 0.55, f"Performance {int(score*100)}% — bajo"
    if score < 0.7:
        return 0.25, f"Performance {int(score*100)}% — promedio"
    return 0.1, f"Performance {int(score*100)}% — desempeño alto"


def _salary_risk(salary: float, dept_avg: float) -> tuple[float, str]:
    """Salario por debajo del promedio del departamento = riesgo."""
    if not dept_avg or dept_avg <= 0 or not salary or salary <= 0:
        return 0.3, "Sin datos suficientes para comparar salario"
    ratio = salary / dept_avg
    if ratio < 0.80:
        return 0.75, f"Salario {int((1-ratio)*100)}% por debajo del avg del equipo"
    if ratio < 0.95:
        return 0.4, f"Salario {int((1-ratio)*100)}% por debajo del avg del equipo"
    if ratio <= 1.10:
        return 0.1, "Salario alineado con el avg del equipo"
    return 0.05, f"Salario {int((ratio-1)*100)}% por encima del avg del equipo"


def _manager_change_risk(changed: bool) -> tuple[float, str]:
    if changed:
        return 0.65, "Cambio de manager en los últimos 6 meses"
    return 0.1, "Sin cambios de manager recientes"


def _engagement_risk(okrs_assigned: int, okrs_progress: float) -> tuple[float, str]:
    if okrs_assigned == 0:
        return 0.7, "Sin OKRs asignados (desenganche o pendiente de asignar)"
    if okrs_progress < 0.2:
        return 0.65, f"OKRs asignados pero progreso {int(okrs_progress*100)}%"
    if okrs_progress < 0.5:
        return 0.35, f"OKRs en marcha — {int(okrs_progress*100)}% completo"
    return 0.1, f"OKRs progresando — {int(okrs_progress*100)}% completo"


# ─── Scorer principal ──────────────────────────────────────────
def score_attrition(emp: EmployeeAttritionInput) -> AttritionResult:
    """Calcula el risk score de fuga de talento con breakdown completo."""
    factors_raw = [
        ("tenure",         "Antigüedad",      *_tenure_risk(emp.hire_date)),
        ("leave_freq",     "Frecuencia de ausencias", *_leave_risk(emp.leaves_last_6m)),
        ("performance",    "Performance",     *_performance_risk(emp.avg_kpi_score)),
        ("salary_band",    "Banda salarial",  *_salary_risk(emp.salary, emp.department_avg_salary)),
        ("manager_change", "Cambio de manager", *_manager_change_risk(emp.manager_changed_within_6m)),
        ("engagement",     "Engagement (OKRs)", *_engagement_risk(emp.okrs_assigned, emp.okrs_avg_progress)),
    ]

    factors: list[AttritionFactor] = []
    total = 0.0
    for code, label, level, rationale in factors_raw:
        w = WEIGHTS[code]
        contribution = level * w * 100
        total += contribution
        factors.append(AttritionFactor(
            code=code, label=label, level=round(level, 3), weight=w,
            contribution=round(contribution, 1), rationale=rationale,
        ))

    score = round(total)
    top = sorted(factors, key=lambda f: f.contribution, reverse=True)[:2]

    return AttritionResult(
        employee_id=emp.employee_id,
        employee_name=emp.name,
        department=emp.department,
        position=emp.position,
        risk_score=score,
        risk_band=_band(score),
        factors=factors,
        top_drivers=[f.label for f in top],
    )

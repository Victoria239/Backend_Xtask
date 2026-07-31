"""Comp analytics (C-06).

Funcionalidades clave
---------------------
- Auto-derivación de seniority desde el title (`vp`, `head`, `senior`, `jr`)
- Bandas P25/P50/P75 por (departamento, seniority) calculadas con numpy
- Detección de outliers: empleados con compa-ratio < 0.85 o > 1.15
- Distribución de payroll por departamento (% y absoluto)
- Top earners + tenure vs salary scatter

Sin sklearn — solo numpy + Python puro, igual que el resto de predictions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import numpy as np


SENIORITY_KEYWORDS = [
    ("lead",   ["vp ", "head of", " cto", " cfo", " ceo", "chief", "director"]),
    ("senior", ["senior", " sr ", " sr."]),
    ("junior", ["junior", "jr.", " jr ", "intern", "trainee"]),
    # default → mid
]


def detect_seniority(position: str | None) -> str:
    if not position:
        return "mid"
    p = f" {position.lower()} "
    for level, keywords in SENIORITY_KEYWORDS:
        if any(k in p for k in keywords):
            return level
    return "mid"


@dataclass
class EmployeeComp:
    employee_id: int
    name: str
    department: str
    position: str
    seniority: str
    salary: float
    hire_date: date | None
    tenure_months: int


@dataclass
class Band:
    department: str
    seniority: str
    headcount: int
    p25: float
    p50: float
    p75: float
    min: float
    max: float


@dataclass
class Outlier:
    employee_id: int
    name: str
    department: str
    position: str
    seniority: str
    salary: float
    band_p50: float
    compa_ratio: float
    flag: str  # "below" | "above"
    delta_eur: float
    reason: str


@dataclass
class CompOverview:
    total_employees: int
    total_payroll_annual: float
    avg_salary: float
    median_salary: float
    gap_factor: float  # max/min
    compa_ratio_avg: float
    departments: list[dict] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)
    outliers: list[Outlier] = field(default_factory=list)
    top_earners: list[dict] = field(default_factory=list)
    tenure_vs_salary: list[dict] = field(default_factory=list)


def _band_for(salaries: list[float]) -> tuple[float, float, float]:
    arr = np.array(salaries, dtype=float)
    return float(np.percentile(arr, 25)), float(np.percentile(arr, 50)), float(np.percentile(arr, 75))


def _months_since(d: date | None) -> int:
    if not d:
        return 0
    return max(0, (date.today() - d).days // 30)


def analyze(employees: list[EmployeeComp]) -> CompOverview:
    if not employees:
        return CompOverview(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    salaries = np.array([e.salary for e in employees if e.salary > 0], dtype=float)
    if salaries.size == 0:
        return CompOverview(len(employees), 0.0, 0.0, 0.0, 0.0, 0.0)

    total_payroll = float(salaries.sum())
    avg_salary = float(salaries.mean())
    median_salary = float(np.median(salaries))
    gap_factor = float(salaries.max() / salaries.min()) if salaries.min() > 0 else 0.0

    # Bandas por (dept, seniority)
    bucket: dict[tuple[str, str], list[float]] = defaultdict(list)
    for e in employees:
        if e.salary > 0:
            bucket[(e.department, e.seniority)].append(e.salary)

    bands: list[Band] = []
    band_p50: dict[tuple[str, str], float] = {}
    for (dept, sen), vals in bucket.items():
        p25, p50, p75 = _band_for(vals)
        bands.append(Band(
            department=dept, seniority=sen, headcount=len(vals),
            p25=round(p25), p50=round(p50), p75=round(p75),
            min=round(min(vals)), max=round(max(vals)),
        ))
        band_p50[(dept, sen)] = p50
    bands.sort(key=lambda b: (b.department, ["junior", "mid", "senior", "lead"].index(b.seniority)))

    # Compa-ratio + outliers
    outliers: list[Outlier] = []
    compa_ratios: list[float] = []
    for e in employees:
        if e.salary <= 0:
            continue
        p50 = band_p50.get((e.department, e.seniority))
        if not p50 or p50 <= 0:
            continue
        ratio = e.salary / p50
        compa_ratios.append(ratio)
        if ratio < 0.90:
            outliers.append(Outlier(
                employee_id=e.employee_id, name=e.name,
                department=e.department, position=e.position, seniority=e.seniority,
                salary=e.salary, band_p50=round(p50), compa_ratio=round(ratio, 3),
                flag="below", delta_eur=round(p50 - e.salary),
                reason=f"{int((1 - ratio) * 100)}% por debajo de la mediana del banda {e.seniority}",
            ))
        elif ratio > 1.10:
            outliers.append(Outlier(
                employee_id=e.employee_id, name=e.name,
                department=e.department, position=e.position, seniority=e.seniority,
                salary=e.salary, band_p50=round(p50), compa_ratio=round(ratio, 3),
                flag="above", delta_eur=round(e.salary - p50),
                reason=f"{int((ratio - 1) * 100)}% por encima de la mediana del banda {e.seniority}",
            ))
    outliers.sort(key=lambda o: abs(1 - o.compa_ratio), reverse=True)

    compa_avg = float(np.mean(compa_ratios)) if compa_ratios else 0.0

    # Distribución por departamento
    dept_totals: dict[str, list[float]] = defaultdict(list)
    for e in employees:
        if e.salary > 0:
            dept_totals[e.department].append(e.salary)
    departments = []
    for dept, vals in sorted(dept_totals.items(), key=lambda kv: -sum(kv[1])):
        total = sum(vals)
        departments.append({
            "department": dept,
            "headcount": len(vals),
            "total_payroll": round(total),
            "avg_salary": round(total / len(vals)),
            "share_pct": round((total / total_payroll) * 100, 1),
        })

    # Top earners
    top_earners = [
        {
            "employee_id": e.employee_id, "name": e.name,
            "department": e.department, "position": e.position,
            "salary": round(e.salary),
        }
        for e in sorted(employees, key=lambda x: -x.salary)[:5]
    ]

    # Tenure vs salary (para scatter)
    tenure_vs_salary = [
        {
            "employee_id": e.employee_id, "name": e.name,
            "department": e.department, "tenure_months": e.tenure_months,
            "salary": round(e.salary),
        }
        for e in employees if e.salary > 0
    ]

    return CompOverview(
        total_employees=len(employees),
        total_payroll_annual=round(total_payroll),
        avg_salary=round(avg_salary),
        median_salary=round(median_salary),
        gap_factor=round(gap_factor, 2),
        compa_ratio_avg=round(compa_avg, 3),
        departments=departments,
        bands=bands,
        outliers=outliers,
        top_earners=top_earners,
        tenure_vs_salary=tenure_vs_salary,
    )

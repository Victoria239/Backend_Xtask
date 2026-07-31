"""People Analytics avanzado (H-07).

Cruza datos que ya existen (employees, attrition, comp, KPIs) en métricas
de talento de nivel HRBP/CHRO:

- Tenure distribution: histograma de antigüedad por buckets.
- Span of control: cuántos reportes directos tiene cada manager.
- 9-box grid: performance (eje X) vs retención (eje Y, inverso del riesgo de
  fuga). Clásico de gestión de talento para identificar high-potentials,
  estrellas en riesgo, y bajo rendimiento.
- Comp band saturation: dónde caen los salarios respecto a P25/P50/P75.
- Segment risk heatmap: riesgo de fuga promedio cruzado por (departamento ×
  seniority).
- Diversity snapshot: distribución headcount + equidad salarial por depto.

Todo rule-based + numpy. Sin ML supervisado.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import numpy as np


# ─── Inputs ─────────────────────────────────────────────────────
@dataclass(frozen=True)
class PersonRow:
    employee_id: int
    name: str
    department: str
    position: str
    seniority: str            # junior | mid | senior | lead
    salary: float
    tenure_months: int
    manager_id: int | None
    performance: float        # 0..1
    attrition_score: int      # 0..100
    attrition_band: str       # low | medium | high


# ─── Tenure buckets ─────────────────────────────────────────────
TENURE_BUCKETS = [
    ("0-6m", 0, 6),
    ("6-12m", 6, 12),
    ("1-2a", 12, 24),
    ("2-4a", 24, 48),
    ("4a+", 48, 9999),
]


def _tenure_bucket(months: int) -> str:
    for label, lo, hi in TENURE_BUCKETS:
        if lo <= months < hi:
            return label
    return "4a+"


# ─── 9-box ──────────────────────────────────────────────────────
# Eje X (performance): bajo <0.4, medio 0.4-0.7, alto >0.7
# Eje Y (retención = 1 - riesgo): bajo (alto riesgo), medio, alto (bajo riesgo)
NINE_BOX_LABELS = {
    (2, 2): "Estrella",            # alto perf + alta retención
    (2, 1): "Alto potencial",      # alto perf + retención media
    (2, 0): "Estrella en riesgo",  # alto perf + baja retención ← ACCIÓN URGENTE
    (1, 2): "Sólido confiable",
    (1, 1): "Core",
    (1, 0): "Core en riesgo",
    (0, 2): "Bajo perf estable",
    (0, 1): "Cuestionable",
    (0, 0): "Bajo rendimiento",
}


def _perf_tier(p: float) -> int:
    return 2 if p > 0.7 else (1 if p >= 0.4 else 0)


def _retention_tier(band: str) -> int:
    # retención alta = riesgo bajo
    return {"low": 2, "medium": 1, "high": 0}.get(band, 1)


@dataclass
class NineBoxCell:
    perf_tier: int
    retention_tier: int
    label: str
    count: int
    employees: list[dict]


@dataclass
class PeopleOverview:
    total_employees: int
    avg_tenure_months: float
    avg_performance: float
    managers_count: int
    tenure_distribution: list[dict] = field(default_factory=list)
    span_of_control: list[dict] = field(default_factory=list)
    nine_box: list[NineBoxCell] = field(default_factory=list)
    segment_risk: list[dict] = field(default_factory=list)
    diversity: list[dict] = field(default_factory=list)
    band_saturation: dict = field(default_factory=dict)


def analyze_people(rows: list[PersonRow]) -> PeopleOverview:
    if not rows:
        return PeopleOverview(0, 0.0, 0.0, 0)

    tenures = np.array([r.tenure_months for r in rows], dtype=float)
    perfs = np.array([r.performance for r in rows], dtype=float)

    # ─── Tenure distribution ───
    bucket_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        bucket_counts[_tenure_bucket(r.tenure_months)] += 1
    tenure_dist = [
        {"bucket": label, "count": bucket_counts.get(label, 0)}
        for label, _, _ in TENURE_BUCKETS
    ]

    # ─── Span of control ───
    reports_by_mgr: dict[int, list[str]] = defaultdict(list)
    name_by_id = {r.employee_id: r.name for r in rows}
    for r in rows:
        if r.manager_id:
            reports_by_mgr[r.manager_id].append(r.name)
    span = [
        {
            "manager_id": mid,
            "manager_name": name_by_id.get(mid, f"#{mid}"),
            "direct_reports": len(reps),
            "reports": reps,
        }
        for mid, reps in reports_by_mgr.items()
    ]
    span.sort(key=lambda s: s["direct_reports"], reverse=True)

    # ─── 9-box grid ───
    cells: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for r in rows:
        pt = _perf_tier(r.performance)
        rt = _retention_tier(r.attrition_band)
        cells[(pt, rt)].append({
            "employee_id": r.employee_id, "name": r.name,
            "department": r.department, "performance": round(r.performance, 2),
            "attrition_score": r.attrition_score,
        })
    nine_box = [
        NineBoxCell(
            perf_tier=pt, retention_tier=rt,
            label=NINE_BOX_LABELS[(pt, rt)],
            count=len(cells.get((pt, rt), [])),
            employees=cells.get((pt, rt), []),
        )
        for pt in (2, 1, 0) for rt in (0, 1, 2)
    ]

    # ─── Segment risk (departamento × seniority) ───
    seg: dict[tuple[str, str], list[int]] = defaultdict(list)
    for r in rows:
        seg[(r.department, r.seniority)].append(r.attrition_score)
    segment_risk = [
        {
            "department": dept, "seniority": sen,
            "headcount": len(scores),
            "avg_risk": round(float(np.mean(scores)), 1),
            "max_risk": int(max(scores)),
        }
        for (dept, sen), scores in seg.items()
    ]
    segment_risk.sort(key=lambda s: s["avg_risk"], reverse=True)

    # ─── Diversity / equity por departamento ───
    dept_rows: dict[str, list[PersonRow]] = defaultdict(list)
    for r in rows:
        dept_rows[r.department].append(r)
    diversity = []
    for dept, drs in sorted(dept_rows.items(), key=lambda kv: -len(kv[1])):
        sals = [d.salary for d in drs if d.salary > 0]
        sen_mix = defaultdict(int)
        for d in drs:
            sen_mix[d.seniority] += 1
        diversity.append({
            "department": dept,
            "headcount": len(drs),
            "avg_salary": round(float(np.mean(sals))) if sals else 0,
            "salary_spread": round(float(np.std(sals))) if len(sals) > 1 else 0,
            "seniority_mix": dict(sen_mix),
        })

    # ─── Band saturation (cuántos under/in/over band P25-P75) ───
    band_pos = {"below_p25": 0, "p25_p50": 0, "p50_p75": 0, "above_p75": 0}
    by_sen: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.salary > 0:
            by_sen[r.seniority].append(r.salary)
    for r in rows:
        if r.salary <= 0:
            continue
        peers = by_sen[r.seniority]
        if len(peers) < 2:
            band_pos["p50_p75"] += 1  # sin comparación, default neutro
            continue
        p25, p50, p75 = (float(np.percentile(peers, q)) for q in (25, 50, 75))
        if r.salary < p25:
            band_pos["below_p25"] += 1
        elif r.salary < p50:
            band_pos["p25_p50"] += 1
        elif r.salary < p75:
            band_pos["p50_p75"] += 1
        else:
            band_pos["above_p75"] += 1

    return PeopleOverview(
        total_employees=len(rows),
        avg_tenure_months=round(float(tenures.mean()), 1),
        avg_performance=round(float(perfs.mean()), 2),
        managers_count=len(reports_by_mgr),
        tenure_distribution=tenure_dist,
        span_of_control=span,
        nine_box=nine_box,
        segment_risk=segment_risk,
        diversity=diversity,
        band_saturation=band_pos,
    )

"""Happy-path tests para H-07 People Analytics (pure functions)."""
from __future__ import annotations

from services.predictions.people_analytics import (
    PersonRow, analyze_people, _tenure_bucket, _perf_tier, _retention_tier,
)


def _person(eid, name, dept="Eng", sen="mid", salary=60000, tenure=24,
            mgr=None, perf=0.6, score=30, band="medium") -> PersonRow:
    return PersonRow(
        employee_id=eid, name=name, department=dept, position="Engineer",
        seniority=sen, salary=salary, tenure_months=tenure, manager_id=mgr,
        performance=perf, attrition_score=score, attrition_band=band,
    )


def test_empty_returns_zeros():
    ov = analyze_people([])
    assert ov.total_employees == 0
    assert ov.nine_box == []
    assert ov.span_of_control == []


def test_tenure_bucket_boundaries():
    assert _tenure_bucket(0) == "0-6m"
    assert _tenure_bucket(5) == "0-6m"
    assert _tenure_bucket(6) == "6-12m"
    assert _tenure_bucket(12) == "1-2a"
    assert _tenure_bucket(24) == "2-4a"
    assert _tenure_bucket(48) == "4a+"
    assert _tenure_bucket(120) == "4a+"


def test_perf_and_retention_tiers():
    assert _perf_tier(0.9) == 2
    assert _perf_tier(0.5) == 1
    assert _perf_tier(0.2) == 0
    assert _retention_tier("low") == 2     # bajo riesgo = alta retención
    assert _retention_tier("high") == 0    # alto riesgo = baja retención
    assert _retention_tier("medium") == 1


def test_nine_box_classifies_star_at_risk():
    """Alto perf + alto riesgo (baja retención) → 'Estrella en riesgo'."""
    rows = [_person(1, "Risky Star", perf=0.9, band="high")]
    ov = analyze_people(rows)
    star_at_risk = next(c for c in ov.nine_box if c.perf_tier == 2 and c.retention_tier == 0)
    assert star_at_risk.label == "Estrella en riesgo"
    assert star_at_risk.count == 1
    assert star_at_risk.employees[0]["name"] == "Risky Star"


def test_nine_box_full_grid_has_9_cells():
    rows = [_person(1, "A")]
    ov = analyze_people(rows)
    assert len(ov.nine_box) == 9  # siempre 3x3 aunque mayoría vacías


def test_span_of_control_counts_reports():
    rows = [
        _person(1, "Manager", mgr=None),
        _person(2, "Report A", mgr=1),
        _person(3, "Report B", mgr=1),
        _person(4, "Solo", mgr=None),
    ]
    ov = analyze_people(rows)
    assert ov.managers_count == 1
    top = ov.span_of_control[0]
    assert top["manager_id"] == 1
    assert top["direct_reports"] == 2
    assert set(top["reports"]) == {"Report A", "Report B"}


def test_segment_risk_aggregates_by_dept_seniority():
    rows = [
        _person(1, "A", dept="Eng", sen="senior", score=70),
        _person(2, "B", dept="Eng", sen="senior", score=50),
        _person(3, "C", dept="Sales", sen="junior", score=20),
    ]
    ov = analyze_people(rows)
    eng_senior = next(s for s in ov.segment_risk if s["department"] == "Eng" and s["seniority"] == "senior")
    assert eng_senior["headcount"] == 2
    assert eng_senior["avg_risk"] == 60.0   # (70+50)/2
    assert eng_senior["max_risk"] == 70
    # Ordenado por avg_risk desc → Eng/senior primero
    assert ov.segment_risk[0]["department"] == "Eng"


def test_band_saturation_classifies_positions():
    # 3 seniors: 40k (below), 60k (mid), 80k (above) → distribución entre buckets
    rows = [
        _person(1, "Low", sen="senior", salary=40000),
        _person(2, "Mid", sen="senior", salary=60000),
        _person(3, "High", sen="senior", salary=80000),
    ]
    ov = analyze_people(rows)
    total = sum(ov.band_saturation.values())
    assert total == 3


def test_diversity_computes_per_department():
    rows = [
        _person(1, "A", dept="Eng", salary=50000),
        _person(2, "B", dept="Eng", salary=70000),
        _person(3, "C", dept="Sales", salary=55000),
    ]
    ov = analyze_people(rows)
    eng = next(d for d in ov.diversity if d["department"] == "Eng")
    assert eng["headcount"] == 2
    assert eng["avg_salary"] == 60000
    assert eng["salary_spread"] > 0  # 50k y 70k tienen dispersión

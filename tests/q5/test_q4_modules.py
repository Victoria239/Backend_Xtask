"""Happy-path tests para módulos Q4.

Cobertura:
- attrition.score_attrition (pure function)
- comp_analytics.analyze (pure function)
- reviews lifecycle (create → assign → submit → close → summary)
- ai_assistant.tools.execute_tool defensive dispatch
- shared.n8n_client.emit_event best-effort behavior
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest_asyncio
from sqlalchemy import text


# ─── attrition (pure) ─────────────────────────────────────────────
def test_attrition_low_risk_for_stable_employee():
    from services.predictions.attrition import EmployeeAttritionInput, score_attrition
    inp = EmployeeAttritionInput(
        employee_id=1, name="Stable Sam", department="Eng", position="Senior Eng",
        hire_date=date(2024, 1, 15), salary=70000.0,
        leaves_last_6m=1, avg_kpi_score=0.85,
        okrs_assigned=2, okrs_avg_progress=0.7,
        manager_changed_within_6m=False, department_avg_salary=72000.0,
    )
    res = score_attrition(inp)
    assert res.risk_band == "low"
    assert res.risk_score < 25
    assert len(res.factors) == 6
    assert sum(f.weight for f in res.factors) == 1.0  # weights normalizados


def test_attrition_high_risk_for_burnout_employee():
    from services.predictions.attrition import EmployeeAttritionInput, score_attrition
    inp = EmployeeAttritionInput(
        employee_id=2, name="Burnt Bob", department="Eng", position="Engineer",
        hire_date=date(2025, 9, 1), salary=35000.0,
        leaves_last_6m=8, avg_kpi_score=0.2,
        okrs_assigned=0, okrs_avg_progress=0.0,
        manager_changed_within_6m=True, department_avg_salary=70000.0,
    )
    res = score_attrition(inp)
    assert res.risk_band == "high"
    assert res.risk_score >= 50
    assert "Frecuencia de ausencias" in res.top_drivers or "Banda salarial" in res.top_drivers


def test_attrition_factors_have_rationale():
    from services.predictions.attrition import EmployeeAttritionInput, score_attrition
    inp = EmployeeAttritionInput(
        employee_id=3, name="Avg Alice", department="Sales", position="AE",
        hire_date=date(2024, 6, 1), salary=50000.0,
        leaves_last_6m=3, avg_kpi_score=0.5,
        okrs_assigned=1, okrs_avg_progress=0.3,
        manager_changed_within_6m=False, department_avg_salary=50000.0,
    )
    res = score_attrition(inp)
    for f in res.factors:
        assert f.rationale  # never empty
        assert 0 <= f.level <= 1
        assert f.contribution >= 0


# ─── comp_analytics (pure) ────────────────────────────────────────
def test_comp_analyze_empty_returns_zeros():
    from services.predictions.comp_analytics import analyze
    ov = analyze([])
    assert ov.total_employees == 0
    assert ov.total_payroll_annual == 0.0
    assert ov.outliers == []


def test_comp_detect_seniority():
    from services.predictions.comp_analytics import detect_seniority
    assert detect_seniority("VP Engineering") == "lead"
    assert detect_seniority("Head of Frontend") == "lead"
    assert detect_seniority("CTO") == "lead"
    assert detect_seniority("Senior Backend Engineer") == "senior"
    assert detect_seniority("Junior Engineer") == "junior"
    assert detect_seniority("Intern") == "junior"
    assert detect_seniority("Backend Engineer") == "mid"
    assert detect_seniority(None) == "mid"
    assert detect_seniority("") == "mid"


def test_comp_analyze_detects_outliers():
    from services.predictions.comp_analytics import EmployeeComp, analyze
    emps = [
        EmployeeComp(1, "A", "Eng", "Senior Eng", "senior", 50000, date(2024, 1, 1), 12),
        EmployeeComp(2, "B", "Eng", "Senior Eng", "senior", 70000, date(2024, 1, 1), 12),
        EmployeeComp(3, "C", "Eng", "Senior Eng", "senior", 90000, date(2024, 1, 1), 12),
    ]
    ov = analyze(emps)
    # Avg salary = 70k; A está a 0.71× p50, debería ser outlier below
    flags = {o.name: o.flag for o in ov.outliers}
    assert "A" in flags and flags["A"] == "below"
    assert "C" in flags and flags["C"] == "above"


# ─── reviews lifecycle (integration con DB real) ─────────────────
async def test_reviews_full_cycle_lifecycle(fresh_session):
    """Crea ciclo → asigna → submitea 1 response → cierra → verifica summary."""
    from services.reviews.service import ReviewsService

    svc = ReviewsService(fresh_session)
    cycle = await svc.create_cycle(
        tenant_id=2, name="Q5 Test Cycle", period="2026-Q5", deadline=None, user_id=None,
    )
    await fresh_session.commit()
    try:
        n = await svc.auto_assign(2, cycle.id)
        await fresh_session.commit()
        assert n > 0  # se crearon asignaciones

        # Tomar una asignación self para submit
        assignment = (await fresh_session.execute(text(
            "SELECT id, reviewer_employee_id FROM svc_reviews.review_assignments "
            "WHERE cycle_id = :c AND role = 'self' LIMIT 1"
        ), {"c": cycle.id})).first()
        assert assignment is not None

        form = await svc.get_form(2, assignment[0], assignment[1])
        responses = [
            {"question_code": q["code"], "score": 4, "comment": "test"}
            for q in form["questions"]
        ]
        await svc.submit(2, assignment[0], assignment[1], responses)
        await fresh_session.commit()

        # Cerrar ciclo y verificar agregación
        res = await svc.close_cycle(2, cycle.id)
        await fresh_session.commit()
        assert res["summaries"] >= 1
    finally:
        # Cleanup
        for s in [
            "DELETE FROM svc_reviews.review_summaries WHERE cycle_id = :c",
            "DELETE FROM svc_reviews.review_responses "
            "WHERE assignment_id IN (SELECT id FROM svc_reviews.review_assignments WHERE cycle_id = :c)",
            "DELETE FROM svc_reviews.review_assignments WHERE cycle_id = :c",
            "DELETE FROM svc_reviews.review_cycles WHERE id = :c",
        ]:
            try:
                await fresh_session.execute(text(s), {"c": cycle.id})
            except Exception:  # noqa: BLE001
                pass
        await fresh_session.commit()


# ─── ai_assistant.tools defensive parsing ────────────────────────
async def test_tool_unknown_returns_error(fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, 2, "nonexistent_tool", {})
    data = json.loads(r)
    assert data.get("error"), "tool desconocido debe devolver error"


async def test_tool_filters_unexpected_kwargs(fresh_session):
    """LLMs pequeños a veces inyectan 'required' como argument. Debe ignorarse."""
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, 2, "get_employee_detail", {
        "employee_id": 1,
        "required": ["employee_id"],   # ← campo del schema, debe filtrarse
        "type": "object",                # ← idem
    })
    # No debe raise; debe ejecutarse aunque el LLM mandó basura del schema
    data = json.loads(r)
    assert "error" not in data or "no encontrado" in str(data.get("error", "")).lower(), (
        f"Tool debería tolerar kwargs del schema; got: {data}"
    )


async def test_tool_definitions_count(fresh_session):
    """Verificar que las 12 tools están registradas."""
    from services.ai_assistant.tools import TOOL_DEFINITIONS, TOOL_HANDLERS
    assert len(TOOL_DEFINITIONS) == 12
    assert len(TOOL_HANDLERS) == 12
    # Cada tool en DEFINITIONS tiene un handler
    for tdef in TOOL_DEFINITIONS:
        name = tdef["function"]["name"]
        assert name in TOOL_HANDLERS, f"Tool {name} declared sin handler"


# ─── shared.n8n_client best-effort ───────────────────────────────
async def test_n8n_emit_when_disabled_returns_false():
    from shared import n8n_client
    with patch.dict(os.environ, {"N8N_ENABLED": "false"}):
        ok = await n8n_client.emit_event("xtask.test", {"x": 1})
    assert ok is False  # disabled → no llamada, retorna False


async def test_n8n_emit_unreachable_returns_false_no_raise():
    """Si n8n está caído, emit_event NUNCA debe romper la operación principal."""
    from shared import n8n_client
    with patch.dict(os.environ, {
        "N8N_ENABLED": "true",
        "N8N_WEBHOOK_BASE": "http://localhost:1",  # puerto inexistente
    }):
        ok = await n8n_client.emit_event("xtask.test", {"x": 1})
    assert ok is False  # falla silenciosa


# ─── BI overview shape ───────────────────────────────────────────
async def test_bi_overview_returns_complete_shape(fresh_session):
    from services.dashboard.bi import build_bi_overview
    result = await build_bi_overview(fresh_session, tenant_id=2)
    for key in ("generated_at", "north_star", "financial", "people", "performance", "revenue"):
        assert key in result, f"Falta key '{key}' en bi overview"
    for k in ("arr_eur", "headcount", "active_clients", "okr_avg_progress"):
        assert k in result["north_star"]
    for k in ("arr_eur", "payroll_annual_eur", "pnl_annual_eur"):
        assert k in result["financial"]


# ─── Portal shape ────────────────────────────────────────────────
async def test_portal_returns_complete_shape(fresh_session):
    from services.dashboard.portal import build_my_portal
    result = await build_my_portal(fresh_session, tenant_id=2, user_id=6)
    assert "profile" in result
    assert "leaves" in result
    assert "reviews_pending" in result
    assert "okrs" in result
    assert "contracts" in result
    assert "benefits_recommended" in result
    assert result["profile"]["employee_id"] > 0

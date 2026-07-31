"""Tests adversariales de aislamiento multi-tenant para módulos Q4."""
from __future__ import annotations

import json

import pytest_asyncio
from sqlalchemy import text

HOME = 2
ALIEN = 999
ALIEN_NAME = "ZZZAlienator"
ALIEN_DEPT = "ZZZAlienDept"
ALIEN_EMAIL = f"{ALIEN_NAME}@alien.test"

ALIEN_MARKERS = (
    ALIEN_NAME, ALIEN_DEPT, "AlienCorp", "Alien Director",
    "Alien KPI", "Alien Review", "ALIEN_PTO",
)


def _assert_no_alien(blob, where: str) -> None:
    s = blob if isinstance(blob, str) else json.dumps(blob, default=str, ensure_ascii=False)
    for marker in ALIEN_MARKERS:
        assert marker not in s, (
            f"❌ {where}: marker '{marker}' del tenant ALIEN={ALIEN} apareció "
            f"al consultar HOME={HOME}. Bug de tenant isolation."
        )


@pytest_asyncio.fixture
async def alien_data(fresh_session):
    db = fresh_session
    uid = (await db.execute(text(
        "INSERT INTO svc_auth.users (username, password, email, full_name, role, is_active) "
        "VALUES (:u, '$2b$12$x', :u, 'Alien', 'member', true) RETURNING id"
    ), {"u": ALIEN_EMAIL})).scalar()
    eid = (await db.execute(text(
        "INSERT INTO svc_employees.employees "
        "(tenant_id, user_id, first_name, last_name, position, department, salary, contract_status, hire_date, custom_fields) "
        "VALUES (:tid, :uid, :fn, 'Alien', 'Alien Director', :dept, 999999, 'active', '2024-01-01', '{}') "
        "RETURNING id"
    ), {"tid": ALIEN, "uid": uid, "fn": ALIEN_NAME, "dept": ALIEN_DEPT})).scalar()
    ltid = (await db.execute(text(
        "INSERT INTO svc_leaves.leave_types "
        "(tenant_id, code, name, accrual_strategy, days_per_year, color, requires_approval, allow_negative_balance, active) "
        "VALUES (:tid, 'ALIEN_PTO', 'Alien Vacation', 'annual_grant', 25, '#000', true, false, true) RETURNING id"
    ), {"tid": ALIEN})).scalar()
    await db.execute(text(
        "INSERT INTO svc_leaves.leaves "
        "(tenant_id, employee_id, type_id, start_date, end_date, business_days, status, reason) "
        "VALUES (:tid, :eid, :ltid, '2026-01-01', '2026-01-05', 5, 'requested', 'Alien leave')"
    ), {"tid": ALIEN, "eid": eid, "ltid": ltid})
    await db.execute(text(
        "INSERT INTO svc_okrs.okrs "
        "(tenant_id, scope, owner_employee_id, owner_department, objective, period, status, progress, weight) "
        "VALUES (:tid, 'individual', :eid, :dept, :obj, '2026-Q3', 'active', 0.5, 1.0)"
    ), {"tid": ALIEN, "eid": eid, "dept": ALIEN_DEPT, "obj": f"Alien objective by {ALIEN_NAME}"})
    await db.execute(text(
        "INSERT INTO svc_contracts.contracts "
        "(tenant_id, employee_id, counterparty, title, contract_type, status, source, starts_on) "
        "VALUES (:tid, :eid, 'AlienCorp', 'Alien Contract', 'saas', 'active', 'seed', '2024-01-01')"
    ), {"tid": ALIEN, "eid": eid})
    cid = (await db.execute(text(
        "INSERT INTO svc_reviews.review_cycles "
        "(tenant_id, name, period, status) VALUES (:tid, 'Alien Review', '2026-Q3', 'open') RETURNING id"
    ), {"tid": ALIEN})).scalar()
    await db.execute(text(
        "INSERT INTO svc_reviews.review_assignments "
        "(tenant_id, cycle_id, reviewer_employee_id, target_employee_id, role, status) "
        "VALUES (:tid, :cid, :eid, :eid, 'self', 'pending')"
    ), {"tid": ALIEN, "cid": cid, "eid": eid})
    await db.execute(text(
        "INSERT INTO svc_kpis.kpis "
        "(tenant_id, employee_id, name, metric_type, target_value, actual_value, weight, period, periodicity, status, validated) "
        "VALUES (:tid, :eid, 'Alien KPI', 'number', 100, 99, 1.0, '2026-Q3', 'quarterly', 'on_track', true)"
    ), {"tid": ALIEN, "eid": eid})
    await db.commit()

    yield {"tenant_id": ALIEN, "user_id": uid, "employee_id": eid,
           "cycle_id": cid, "leave_type_id": ltid}

    for sql in [
        "DELETE FROM svc_kpis.kpis WHERE tenant_id = :tid",
        "DELETE FROM svc_reviews.review_assignments WHERE tenant_id = :tid",
        "DELETE FROM svc_reviews.review_cycles WHERE tenant_id = :tid",
        "DELETE FROM svc_contracts.contracts WHERE tenant_id = :tid",
        "DELETE FROM svc_okrs.okrs WHERE tenant_id = :tid",
        "DELETE FROM svc_leaves.leaves WHERE tenant_id = :tid",
        "DELETE FROM svc_leaves.leave_types WHERE tenant_id = :tid",
        "DELETE FROM svc_employees.employees WHERE tenant_id = :tid",
    ]:
        try:
            await db.execute(text(sql), {"tid": ALIEN})
        except Exception:  # noqa: BLE001
            pass
    await db.execute(text("DELETE FROM svc_auth.users WHERE email = :e"), {"e": ALIEN_EMAIL})
    await db.commit()


# ─── BI overview ──────────────────────────────────────────────────
async def test_bi_overview_does_not_leak_alien(alien_data, fresh_session):
    from services.dashboard.bi import build_bi_overview
    result = await build_bi_overview(fresh_session, tenant_id=HOME)
    _assert_no_alien(result, "build_bi_overview(home)")


async def test_portal_does_not_leak_alien(alien_data, fresh_session):
    from services.dashboard.portal import build_my_portal
    result = await build_my_portal(fresh_session, tenant_id=HOME, user_id=6)
    _assert_no_alien(result, "build_my_portal(home, user=6)")


async def test_attrition_all_does_not_leak_alien(alien_data, fresh_session):
    from services.predictions.attrition import score_attrition
    from services.predictions.attrition_loader import build_attrition_input
    rows = (await fresh_session.execute(text(
        "SELECT id, first_name, last_name, position, department, hire_date, salary "
        "FROM svc_employees.employees WHERE tenant_id = :tid"
    ), {"tid": HOME})).all()
    results = []
    for r in rows:
        inp = await build_attrition_input(fresh_session, HOME, r)
        results.append(score_attrition(inp))
    blob = [{"name": r.employee_name, "dept": r.department} for r in results]
    _assert_no_alien(blob, "attrition/all(home)")


async def test_comp_analysis_does_not_leak_alien(alien_data, fresh_session):
    from datetime import date as _date
    from services.predictions.comp_analytics import EmployeeComp, analyze, detect_seniority
    rows = (await fresh_session.execute(text(
        "SELECT id, first_name, last_name, department, position, salary, hire_date "
        "FROM svc_employees.employees WHERE tenant_id = :tid"
    ), {"tid": HOME})).all()
    emps = [EmployeeComp(employee_id=r[0], name=f"{r[1]} {r[2]}",
        department=r[3] or "—", position=r[4] or "—", seniority=detect_seniority(r[4]),
        salary=float(r[5] or 0), hire_date=r[6],
        tenure_months=max(0, (_date.today()-r[6]).days//30) if r[6] else 0) for r in rows if r[5]]
    ov = analyze(emps)
    blob = {"departments": ov.departments, "outliers": [o.__dict__ for o in ov.outliers],
            "top_earners": ov.top_earners}
    _assert_no_alien(blob, "comp_analytics(home)")


async def test_reviews_cycles_does_not_leak_alien(alien_data, fresh_session):
    from services.reviews.service import ReviewsService
    cycles = await ReviewsService(fresh_session).list_cycles(HOME)
    _assert_no_alien(cycles, "reviews/cycles(home)")
    for c in cycles:
        assert c["name"] != "Alien Review", "Ciclo del ALIEN visible desde HOME!"


async def test_ai_tool_search_employees_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "search_employees", {"name": "Alien"})
    _assert_no_alien(r, "tool:search_employees(home, name=Alien)")


async def test_ai_tool_get_employee_detail_blocks_cross_tenant(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "get_employee_detail",
                           {"employee_id": alien_data["employee_id"]})
    data = json.loads(r)
    assert data.get("error"), (
        f"❌ get_employee_detail con eid={alien_data['employee_id']} del ALIEN "
        f"desde HOME={HOME} devolvió perfil; debería ser 'no encontrado'. Got: {data}"
    )


async def test_ai_tool_count_headcount_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "count_headcount_by_team", {})
    _assert_no_alien(r, "tool:count_headcount_by_team(home)")


async def test_ai_tool_get_okrs_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "get_okrs", {})
    _assert_no_alien(r, "tool:get_okrs(home)")


async def test_ai_tool_list_contracts_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "list_contracts", {})
    _assert_no_alien(r, "tool:list_contracts(home)")


async def test_ai_tool_pending_leaves_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "pending_leaves", {})
    _assert_no_alien(r, "tool:pending_leaves(home)")


async def test_ai_tool_attrition_summary_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "get_attrition_summary", {})
    _assert_no_alien(r, "tool:get_attrition_summary(home)")


async def test_ai_tool_employee_attrition_blocks_cross_tenant(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "get_employee_attrition",
                           {"employee_id": alien_data["employee_id"]})
    data = json.loads(r)
    assert data.get("error"), "❌ get_employee_attrition cross-tenant no devolvió error"


async def test_ai_tool_comp_analysis_does_not_leak(alien_data, fresh_session):
    from services.ai_assistant.tools import execute_tool
    r = await execute_tool(fresh_session, HOME, "get_comp_analysis", {})
    _assert_no_alien(r, "tool:get_comp_analysis(home)")

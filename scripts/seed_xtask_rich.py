"""Seed rich and coherent XTask data — mirrors the Obsidian vault.

Diseño
------
Por cada entidad de la bóveda (empleados, proyectos, OKRs, contratos),
creamos su contraparte en DB con `tenant_id=2` (el seed default). Eso
hace que el Asistente IA vea los MISMOS nombres en tools (DB) y en
citaciones (vault RAG) — consistencia narrativa.

Mix intencional de perfiles de attrition (AI-06)
------------------------------------------------
Para demostrar la usabilidad del scoring:
- 2 alto riesgo (vested + bajo perf + muchas ausencias + salario bajo)
- 4 medio riesgo (señales mixtas)
- 8 bajo riesgo (perfiles saludables)

Idempotente
-----------
Si encuentra "Ana Martínez" en svc_employees ya cargada, salta. Para
re-seedear: borrar manualmente los registros del tenant 2 primero.

Uso:
    docker compose exec employees python -m scripts.seed_xtask_rich
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Add /app to path for relative imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from shared.database import async_session


TENANT = 2


# (last_name, first_name, position, department, hire_date, salary, manager_lastname, risk_profile)
EMPLOYEES = [
    # Founders / Heads — bajo riesgo (vested but engaged)
    ("López",     "Carlos",    "VP Engineering",        "Engineering", "2023-01-10", 110000, None,         "low"),
    ("Fernández", "Lucía",     "Head of Frontend",      "Engineering", "2023-04-22",  98000, None,         "low"),
    ("Sanz",      "Diego",     "Head of Data & AI",     "Engineering", "2023-09-15",  95000, None,         "low"),
    ("Vidal",     "María",     "Head of Product",       "Product",     "2023-06-05",  92000, None,         "low"),
    ("Ríos",      "Patricia",  "Head of People",        "People",      "2023-11-12",  88000, None,         "low"),
    ("Mora",      "Andrés",    "CFO",                   "Operations",  "2023-02-01", 105000, None,         "low"),
    # Senior con riesgo medio
    ("Martínez",  "Ana",       "Senior Backend Engineer","Engineering","2024-03-15", 65000, "López",       "medium"),
    ("Soto",      "Javier",    "Senior Frontend Engineer","Engineering","2024-01-08", 68000, "Fernández",  "low"),
    # Mid level
    ("Ruiz",      "Pedro",     "Backend Engineer",      "Engineering", "2024-09-01",  52000, "López",      "medium"),
    ("Ortega",    "Tomás",     "Product Manager",       "Product",     "2024-08-19",  58000, "Vidal",      "low"),
    ("Castro",    "Elena",     "UI/UX Designer",        "Engineering", "2024-11-10",  54000, "Fernández",  "low"),
    ("Herrera",   "Sofía",     "Data Scientist",        "Engineering", "2025-02-03",  56000, "Sanz",       "medium"),
    # Junior / soporte
    ("García",    "María",     "Backend Engineer Jr",   "Engineering", "2025-06-20",  38000, "Martínez",   "high"),  # bajo salario + alta freq leaves
    ("Bravo",     "Carla",     "Office Manager",        "Operations",  "2024-05-15",  32000, "Mora",       "high"),  # vested-ish + bajo perf
]


# KPI por employee — (employee_lastname, kpi_name, status, actual, target)
KPI_BY_EMPLOYEE: dict[str, list[tuple[str, str, float, float]]] = {
    # high performers
    "López":     [("Velocidad de equipo", "on_track", 95, 100), ("Uptime", "on_track", 99.8, 99.5)],
    "Fernández": [("CSAT diseño",         "on_track", 4.6, 4.5), ("Bugs UI/sprint", "on_track", 2, 3)],
    "Sanz":      [("Cobertura modelos",   "on_track", 88, 85), ("Tiempo inferencia", "on_track", 120, 200)],
    "Vidal":     [("NPS producto",        "on_track", 52, 50)],
    "Ríos":      [("Tiempo cobertura vacante", "on_track", 35, 45)],
    "Mora":      [("Días cierre mensual", "on_track", 5, 7)],
    "Martínez":  [("Story points/sprint", "on_track", 22, 25), ("PRs reviewed", "behind", 8, 15)],
    "Soto":      [("Lighthouse score",    "on_track", 92, 90)],
    "Ruiz":      [("Story points/sprint", "behind",   14, 25), ("Bugs intro/sprint", "behind", 4, 2)],
    "Ortega":    [("Sprints sin overflow","on_track", 4, 4)],
    "Castro":    [("Componentes shipped", "on_track", 12, 10)],
    "Herrera":   [("Modelos en prod",     "behind",    1, 3), ("MAPE modelos", "behind", 18, 12)],
    "García":    [("Story points/sprint", "behind",    8, 18), ("PRs mergeados", "behind", 3, 8)],
    "Bravo":     [("Tareas administrativas", "behind", 15, 25)],
}


# Leaves seed — (employee_lastname, type_code, days_offset, duration)
# offset = días desde hoy hacia atrás (negativo = futuro)
LEAVES = [
    # María García (high risk — burnout: 6 ausencias en 6m)
    ("García",   "PTO",      -150, 2),
    ("García",   "SICK",     -120, 1),
    ("García",   "SICK",      -90, 2),
    ("García",   "PERSONAL", -60,  1),
    ("García",   "SICK",      -30, 1),
    ("García",   "PTO",       -10, 3),
    # Carla Bravo (high risk — 4 ausencias)
    ("Bravo",    "SICK",     -180, 3),
    ("Bravo",    "SICK",     -120, 1),
    ("Bravo",    "SICK",      -45, 2),
    ("Bravo",    "PERSONAL", -15,  1),
    # Pedro Ruiz (medium — 3 ausencias)
    ("Ruiz",     "PTO",      -100, 5),
    ("Ruiz",     "SICK",      -50, 1),
    ("Ruiz",     "PTO",       -10, 2),
    # Sofía Herrera (medium — 2 ausencias)
    ("Herrera",  "PTO",      -90,  4),
    ("Herrera",  "PERSONAL",-40,   1),
    # Ana Martínez (medium — 2 ausencias)
    ("Martínez", "PTO",      -120, 5),
    ("Martínez", "PTO",      -20,  3),
    # Lows — 0-1 ausencia
    ("Soto",     "PTO",      -60,  7),
    ("Vidal",    "PTO",     -180,  10),
    ("Castro",   "PTO",      -30,  2),
]


# Leave types catalog
LEAVE_TYPES = [
    ("PTO",      "Vacaciones",       25, "#02BDEA"),
    ("SICK",     "Enfermedad",       0,  "#D14040"),
    ("PERSONAL", "Asuntos propios",  3,  "#9B5BFF"),
]


# OKRs — (objective, scope, owner_lastname, dept, period, progress)
OKRS = [
    ("Soportar 10x carga sin degradación de latencia", "department", "López",     "Engineering", "2026-Q3", 0.65),
    ("Reducir tiempo de cierre contrato a 3 días",     "department", "Vidal",     "Product",     "2026-Q3", 0.80),
    ("Habilitar decisiones data-driven en RRHH",       "department", "Sanz",      "Engineering", "2026-Q3", 0.55),
    ("Operar 30 tenants sin proceso manual",           "department", "Ríos",      "People",      "2026-Q3", 0.42),
    ("Migrar a Kubernetes para alta disponibilidad",   "department", "López",     "Engineering", "2026-Q4", 0.10),
    ("Empleados rampan a productivo en < 30 días",     "department", "Ríos",      "People",      "2026-Q4", 0.00),
    # Individuales
    ("Liderar refactor microservicios",                "individual", "Martínez",  "Engineering", "2026-Q3", 0.70),
    ("Cerrar onboarding técnico del backend Jr",       "individual", "Ruiz",      "Engineering", "2026-Q3", 0.30),
    # Sin OKRs asignados: García, Bravo, Castro → engagement risk
]


# Contracts client + employee
CONTRACTS = [
    # Clientes
    ("Acme Corp",         "Contrato Acme XTask v2 SaaS",       "saas",    "active",  "2024-01-15", "2027-01-14", None),
    ("Globex Industries", "Contrato Globex Suscripción Anual", "saas",    "active",  "2024-06-01", "2026-06-01", None),
    ("Initech Solutions", "Contrato Initech Pilot 6m",         "pilot",   "active",  "2025-03-10", "2026-09-10", None),
    ("Stark Logistics",   "Contrato Stark Multipaís",          "saas",    "active",  "2025-09-22", "2027-09-21", None),
    # Empleados (employee_lastname → resolve later)
    ("Ana Martínez",      "Contrato Ana Martínez Indefinido",  "labor",   "active",  "2024-03-15", None,         "Martínez"),
    ("Carlos López",      "Contrato Carlos López Indefinido",  "labor",   "active",  "2023-01-10", None,         "López"),
]


# Projects
PROJECTS = [
    ("Plataforma XTask v2",        "Refactor del core a microservicios",                    "active"),
    ("Integración DocuSign",       "Bridge eSign API",                                       "active"),
    ("Motor de Predicciones KPI",  "Forecasting con numpy",                                  "active"),
    ("Dashboard Admin Multi-tenant","Panel SuperAdmin",                                      "active"),
    ("Onboarding 2.0",             "Rediseño con gamificación",                              "paused"),
    ("Migración a Kubernetes",     "Salida de Compose a K8s",                                "paused"),
]


# ─── Main seeder ───────────────────────────────────────────────
async def seed(db):
    # Idempotencia
    existing = (await db.execute(
        text("SELECT COUNT(*) FROM svc_employees.employees WHERE tenant_id = :t AND last_name = 'López' AND first_name = 'Carlos'"),
        {"t": TENANT},
    )).scalar()
    if existing:
        print("⚠️  Dataset rico ya cargado (Carlos López existe). Salgo sin tocar nada.")
        return

    print("🌱 Sembrando dataset rico para tenant_id=2 ...")

    # ─── Auth users (stub per empleado) ─────────────────────────
    user_to_id: dict[str, int] = {}
    for last, first, *_ in EMPLOYEES:
        email = f"{first.lower()}.{last.lower().replace('í','i').replace('ó','o').replace('é','e').replace('á','a').replace('ñ','n')}@xtask.demo"
        uid = (await db.execute(text(
            "INSERT INTO svc_auth.users (username, password, email, full_name, role, is_active) "
            "VALUES (:u, :p, :e, :n, 'member', true) RETURNING id"
        ), {"u": email, "p": "$2b$12$seed_no_login_placeholder",
            "e": email, "n": f"{first} {last}"})).scalar()
        user_to_id[last] = uid

    # ─── Employees ──────────────────────────────────────────────
    last_to_id: dict[str, int] = {}
    for last, first, pos, dept, hire, sal, mgr_last, _risk in EMPLOYEES:
        # Resolve manager_id later (multi-pass)
        eid = (await db.execute(text(
            "INSERT INTO svc_employees.employees "
            "(tenant_id, user_id, first_name, last_name, position, department, salary, contract_status, hire_date, custom_fields, created_at, updated_at) "
            "VALUES (:tid, :uid, :first, :last, :pos, :dept, :sal, 'active', :hire, :cf, :cre, :upd) "
            "RETURNING id"
        ), {
            "tid": TENANT, "uid": user_to_id[last],
            "first": first, "last": last, "pos": pos, "dept": dept, "sal": sal,
            "hire": date.fromisoformat(hire),
            "cf": json.dumps({}),
            # created_at = hire_date (so attrition manager_change heuristic uses real signal)
            "cre": datetime.fromisoformat(hire), "upd": datetime.fromisoformat(hire),
        })).scalar()
        last_to_id[last] = eid
    print(f"  ✓ {len(EMPLOYEES)} empleados creados (+ users auth)")

    # Manager links + simular cambios de manager recientes (medium/high risk)
    for last, _, _, _, _, _, mgr_last, risk in EMPLOYEES:
        if not mgr_last:
            continue
        mgr_id = last_to_id.get(mgr_last)
        if not mgr_id:
            continue
        if risk in ("medium", "high"):
            # Manager change reciente: updated_at != created_at and < 6m ago
            recent = datetime.now(timezone.utc) - timedelta(days=45)
            await db.execute(text(
                "UPDATE svc_employees.employees SET manager_id = :mid, updated_at = :upd "
                "WHERE id = :eid AND tenant_id = :tid"
            ), {"mid": mgr_id, "upd": recent, "eid": last_to_id[last], "tid": TENANT})
        else:
            await db.execute(text(
                "UPDATE svc_employees.employees SET manager_id = :mid WHERE id = :eid AND tenant_id = :tid"
            ), {"mid": mgr_id, "eid": last_to_id[last], "tid": TENANT})

    # ─── KPIs ────────────────────────────────────────────────────
    kpi_n = 0
    for last, kpis in KPI_BY_EMPLOYEE.items():
        eid = last_to_id.get(last)
        if not eid:
            continue
        for name, status, actual, target in kpis:
            await db.execute(text(
                "INSERT INTO svc_kpis.kpis "
                "(tenant_id, employee_id, name, metric_type, target_value, actual_value, weight, period, periodicity, status, validated) "
                "VALUES (:tid, :eid, :name, 'number', :tgt, :act, 1.0, '2026-Q3', 'quarterly', :st, true)"
            ), {"tid": TENANT, "eid": eid, "name": name, "tgt": target, "act": actual, "st": status})
            kpi_n += 1
    print(f"  ✓ {kpi_n} KPIs creados")

    # ─── Leave types + leaves ───────────────────────────────────
    type_to_id: dict[str, int] = {}
    for code, name, days, color in LEAVE_TYPES:
        tid = (await db.execute(text(
            "INSERT INTO svc_leaves.leave_types "
            "(tenant_id, code, name, accrual_strategy, days_per_year, color, requires_approval, allow_negative_balance, active) "
            "VALUES (:tid, :code, :name, 'annual_grant', :days, :color, true, false, true) "
            "ON CONFLICT DO NOTHING RETURNING id"
        ), {"tid": TENANT, "code": code, "name": name, "days": days, "color": color})).scalar()
        if not tid:
            tid = (await db.execute(text(
                "SELECT id FROM svc_leaves.leave_types WHERE tenant_id = :tid AND code = :code"
            ), {"tid": TENANT, "code": code})).scalar()
        type_to_id[code] = tid

    for emp_last, type_code, offset, dur in LEAVES:
        eid = last_to_id.get(emp_last)
        type_id = type_to_id.get(type_code)
        if not eid or not type_id:
            continue
        start = date.today() - timedelta(days=abs(offset))
        end = start + timedelta(days=dur)
        await db.execute(text(
            "INSERT INTO svc_leaves.leaves "
            "(tenant_id, employee_id, type_id, start_date, end_date, business_days, status, reason) "
            "VALUES (:tid, :eid, :type, :start, :end, :bd, 'approved', 'Solicitud aprobada')"
        ), {"tid": TENANT, "eid": eid, "type": type_id, "start": start, "end": end, "bd": dur})
    print(f"  ✓ {len(LEAVES)} ausencias creadas + {len(LEAVE_TYPES)} tipos")

    # ─── OKRs ───────────────────────────────────────────────────
    for obj, scope, owner_last, dept, period, progress in OKRS:
        owner_id = last_to_id.get(owner_last) if scope == "individual" else None
        await db.execute(text(
            "INSERT INTO svc_okrs.okrs "
            "(tenant_id, scope, owner_employee_id, owner_department, objective, period, status, progress, weight) "
            "VALUES (:tid, :sc, :own, :dept, :obj, :p, 'active', :prog, 1.0)"
        ), {"tid": TENANT, "sc": scope, "own": owner_id, "dept": dept,
            "obj": obj, "p": period, "prog": progress})
    print(f"  ✓ {len(OKRS)} OKRs creados")

    # ─── Contracts ──────────────────────────────────────────────
    # Contratos cliente apuntan al CFO como firmante interno
    cfo_id = last_to_id["Mora"]
    for parte, title, ctype, status, starts, expires, emp_last in CONTRACTS:
        if emp_last:
            eid = last_to_id.get(emp_last)
            counterparty = None
        else:
            eid = cfo_id
            counterparty = parte
        await db.execute(text(
            "INSERT INTO svc_contracts.contracts "
            "(tenant_id, employee_id, counterparty, title, contract_type, status, source, starts_on, expires_on) "
            "VALUES (:tid, :eid, :cp, :title, :ct, :st, 'seed', :starts, :expires)"
        ), {
            "tid": TENANT, "eid": eid, "cp": counterparty, "title": title,
            "ct": ctype, "st": status,
            "starts": date.fromisoformat(starts),
            "expires": date.fromisoformat(expires) if expires else None,
        })
    print(f"  ✓ {len(CONTRACTS)} contratos creados")

    # ─── Projects ──────────────────────────────────────────────
    for name, descr, status in PROJECTS:
        await db.execute(text(
            "INSERT INTO svc_projects.projects (name, description, status, start_date) "
            "VALUES (:n, :d, :s, NOW())"
        ), {"n": name, "d": descr, "s": status})
    print(f"  ✓ {len(PROJECTS)} proyectos creados")

    await db.commit()
    print(f"\n✅ Seed completo. tenant_id={TENANT}")
    print(f"   Distribución de riesgo prevista en attrition:")
    high = sum(1 for *_, r in EMPLOYEES if r == "high")
    med  = sum(1 for *_, r in EMPLOYEES if r == "medium")
    low  = sum(1 for *_, r in EMPLOYEES if r == "low")
    print(f"   · {high} alto · {med} medio · {low} bajo")


async def main():
    async with async_session() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())

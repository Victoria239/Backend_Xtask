"""Fallback determinístico del Asistente cuando el LLM no está disponible.

Por qué existe
--------------
El LLM local (Ollama) puede fallar por falta de memoria (OOM) o por estar
apagado. Sin este fallback, el usuario recibiría un error 500 en cada consulta.

Con este fallback, el Asistente:
1. Detecta la intención de la pregunta por palabras clave.
2. Ejecuta directamente la tool de base de datos correspondiente.
3. Formatea una respuesta legible con los datos reales + el contexto del corpus.

No es tan fluido como una respuesta de LLM, pero SIEMPRE da información útil y
nunca rompe. Es 100% determinístico y auditable.
"""
from __future__ import annotations

import json
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_assistant.tools import execute_tool


def _norm(s: str) -> str:
    """Minúsculas sin acentos, para matchear keywords de forma robusta."""
    s = s.lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Reglas de intención: (keywords, tool_name, args). El orden importa — la primera
# regla que matchee gana.
INTENT_RULES: list[tuple[list[str], str, dict]] = [
    (["cuantos empleados", "cuanta gente", "headcount", "cantidad de empleados",
      "empleados por", "gente por departamento", "plantilla"],
     "count_headcount_by_team", {}),
    (["riesgo de fuga", "riesgo de irse", "se va a ir", "attrition",
      "fuga de talento", "alto riesgo", "retencion"],
     "get_attrition_summary", {}),
    (["sueldo", "salario", "salarial", "banda", "compensacion", "outlier",
      "compa", "paga de mas", "paga de menos", "equidad"],
     "get_comp_analysis", {}),
    (["okr", "objetivo", "objetivos del trimestre", "key result"],
     "get_okrs", {}),
    (["contrato", "contratos", "que clientes tenemos", "lista de clientes"],
     "list_contracts", {}),
    # OJO: solo intenciones de "listar ausencias pendientes", NO preguntas de
    # política ("¿cuántos días de vacaciones tengo?") que deben ir a RAG.
    (["ausencias pendientes", "permisos pendientes", "vacaciones pendientes",
      "pendientes de aprob", "por aprobar", "solicitudes de ausencia",
      "quien pidio", "quien solicito", "ausencias por aprobar",
      "ausencias hay pendientes", "permisos hay pendientes", "hay pendientes"],
     "pending_leaves", {}),
    (["proyecto", "proyectos"],
     "list_projects", {}),
    (["pago", "pagos", "comision", "payout"],
     "recent_payouts", {}),
]


def detect_intent(question: str) -> tuple[str, dict] | None:
    """Devuelve (tool_name, args) si la pregunta matchea una intención conocida."""
    q = _norm(question)
    for keywords, tool, args in INTENT_RULES:
        if any(k in q for k in keywords):
            return tool, args
    return None


def _humanize_tool_result(tool: str, data: dict) -> str:
    """Convierte el JSON de una tool en texto legible en español."""
    if "error" in data:
        return f"No pude obtener esos datos: {data['error']}"

    if tool == "count_headcount_by_team":
        total = data.get("total", 0)
        rows = data.get("by_department", [])
        lines = [f"La empresa tiene {total} empleados activos, distribuidos así:"]
        for r in rows:
            lines.append(f"  • {r['department']}: {r['headcount']}")
        return "\n".join(lines)

    if tool == "get_attrition_summary":
        c = data.get("counts", {})
        top = data.get("top_high_risks", [])
        lines = [
            f"Riesgo de fuga de talento (sobre {data.get('total', 0)} empleados):",
            f"  • Alto riesgo: {c.get('high', 0)}",
            f"  • Riesgo medio: {c.get('medium', 0)}",
            f"  • Bajo riesgo: {c.get('low', 0)}",
        ]
        if top:
            lines.append("\nEmpleados en alto riesgo:")
            for e in top:
                drivers = ", ".join(e.get("drivers", []))
                lines.append(f"  • {e['name']} ({e.get('department', '—')}) — score {e['score']}"
                             + (f" · factores: {drivers}" if drivers else ""))
        return "\n".join(lines)

    if tool == "get_comp_analysis":
        lines = [
            f"Análisis de compensación:",
            f"  • Masa salarial anual: €{data.get('total_payroll_annual', 0):,.0f}",
            f"  • Salario promedio: €{data.get('avg_salary', 0):,.0f}",
            f"  • Salario mediano: €{data.get('median_salary', 0):,.0f}",
            f"  • Factor de brecha (máx/mín): {data.get('gap_factor', 0)}×",
        ]
        outliers = data.get("outliers", [])
        if outliers:
            lines.append("\nEmpleados fuera de su banda salarial:")
            for o in outliers:
                signo = "por debajo" if o["flag"] == "below" else "por encima"
                lines.append(f"  • {o['name']} ({o.get('seniority', '—')}): "
                             f"€{int(o['salary']):,} — {signo} de su banda ({o['reason']})")
        else:
            lines.append("\nNo se detectaron empleados fuera de banda.")
        return "\n".join(lines)

    if tool == "get_okrs":
        rows = data.get("results", [])
        if not rows:
            return "No hay OKRs registrados para ese período."
        lines = [f"OKRs ({data.get('count', len(rows))}):"]
        for o in rows:
            prog = o.get("progress")
            prog_str = f" — {int(float(prog) * 100)}%" if prog is not None and float(prog) <= 1 else (f" — {prog}%" if prog is not None else "")
            lines.append(f"  • {o.get('objective', '—')} ({o.get('period', '—')}, {o.get('status', '—')}){prog_str}")
        return "\n".join(lines)

    if tool == "list_contracts":
        rows = data.get("results", [])
        if not rows:
            return "No hay contratos registrados."
        lines = [f"Contratos ({data.get('count', len(rows))}):"]
        for c in rows:
            who = c.get("counterparty") or (f"empleado #{c['employee_id']}" if c.get("employee_id") else "—")
            lines.append(f"  • {c.get('title', '—')} — {who} · {c.get('status', '—')}")
        return "\n".join(lines)

    if tool == "pending_leaves":
        rows = data.get("results", [])
        if not rows:
            return "No hay ausencias pendientes de aprobación."
        lines = [f"Ausencias pendientes ({data.get('count', len(rows))}):"]
        for l in rows:
            name = f"{l.get('first_name', '')} {l.get('last_name', '')}".strip() or f"empleado #{l.get('employee_id')}"
            lines.append(f"  • {name}: {l.get('start_date')} a {l.get('end_date')} ({l.get('business_days')} días)")
        return "\n".join(lines)

    if tool == "list_projects":
        rows = data.get("results", [])
        if not rows:
            return "No hay proyectos registrados."
        lines = [f"Proyectos ({data.get('count', len(rows))}):"]
        for pr in rows:
            lines.append(f"  • {pr.get('name', '—')} — {pr.get('status', '—')}")
        return "\n".join(lines)

    if tool == "recent_payouts":
        rows = data.get("results", [])
        if not rows:
            return "No hay pagos recientes registrados."
        lines = [f"Pagos recientes ({data.get('count', len(rows))}):"]
        for p in rows:
            lines.append(f"  • {p.get('employee_name', '—')} ({p.get('department', '—')}): €{p.get('amount', 0)}")
        return "\n".join(lines)

    # Genérico
    return json.dumps(data, ensure_ascii=False, indent=2)[:800]


async def answer_from_intent(
    db: AsyncSession,
    tenant_id: int,
    question: str,
) -> tuple[str, str, dict] | None:
    """Camino PRINCIPAL para preguntas de datos.

    Si la pregunta tiene una intención de datos clara, ejecuta la tool y formatea
    una respuesta exacta (sin pasar por el LLM, que con modelos pequeños alucina).

    Returns (answer_text, tool_name, tool_data) o None si no hay intención clara.
    """
    intent = detect_intent(question)
    if not intent:
        return None
    tool, args = intent
    raw = await execute_tool(db, tenant_id, tool, args)
    data = json.loads(raw)
    return _humanize_tool_result(tool, data), tool, data


async def build_fallback_answer(
    db: AsyncSession,
    tenant_id: int,
    question: str,
    rag_context_titles: list[str],
) -> tuple[str, str | None, dict | None]:
    """Fallback cuando el LLM falla en una pregunta CONCEPTUAL (sin intención de datos).

    Returns (answer_text, tool_used_or_None, tool_raw_result_or_None)
    """
    # Por si acaso la pregunta sí tenía intención de datos.
    res = await answer_from_intent(db, tenant_id, question)
    if res:
        body, tool, data = res
        prefix = ("(El asistente conversacional no está disponible, pero consulté "
                  "los datos directamente.)\n\n")
        return prefix + body, tool, data

    if rag_context_titles:
        titles = ", ".join(dict.fromkeys(rag_context_titles))
        body = (
            f"Encontré información relacionada en estos documentos del corpus: {titles}. "
            "Abrí las citas de abajo para leer los fragmentos relevantes."
        )
        return body, None, None

    return (
        "No encontré datos ni documentos que respondan tu pregunta. Probá "
        "reformularla, por ejemplo: \"¿cuántos empleados hay por departamento?\" "
        "o \"¿quién está en alto riesgo de fuga?\"."
    ), None, None

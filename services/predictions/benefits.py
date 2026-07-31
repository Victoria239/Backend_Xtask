"""Motor de recomendación de beneficios (AI-05).

Diseño:
- Catálogo de beneficios con prerequisites y costos.
- Por cada empleado: calculamos score = tenure_weight + perf_weight + skills_weight + role_weight.
- Filtramos por presupuesto y devolvemos top-N con justificación textual.

No usamos ML por ahora — son reglas + collaborative similarity sobre features simples.
Es lo bastante interpretable para que RH valide la sugerencia.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Benefit:
    code: str
    name: str
    category: str  # learning | wellness | financial | flexibility | recognition
    monthly_cost_eur: float
    description: str
    min_tenure_months: int = 0
    min_performance: float = 0.0  # avg KPI status threshold [0..1]


CATALOG: list[Benefit] = [
    Benefit("learn_udemy", "Suscripción Udemy/Coursera", "learning", 30,
            "Acceso ilimitado a cursos online de upskilling.", 0, 0.0),
    Benefit("learn_books", "Stipend de libros", "learning", 20,
            "Reembolso mensual de libros técnicos o de management.", 0, 0.0),
    Benefit("learn_conf", "Conferencia anual", "learning", 200,
            "Cobertura de un evento internacional con viaje incluido.", 12, 0.7),
    Benefit("well_gym", "Gimnasio o ClassPass", "wellness", 50,
            "Plan mensual de gym o ClassPass.", 0, 0.0),
    Benefit("well_therapy", "Sesiones de terapia", "wellness", 80,
            "4 sesiones mensuales con psicólogo via Telehealth.", 3, 0.0),
    Benefit("well_meal", "Vales de comida", "wellness", 100,
            "Tickets restaurant para días de oficina.", 0, 0.0),
    Benefit("fin_pension", "Plan de pensiones", "financial", 150,
            "Aporte mensual matched 50%.", 6, 0.0),
    Benefit("fin_stocks", "Stock options", "financial", 0,
            "Programa de opciones sobre acciones para senior+.", 24, 0.8),
    Benefit("flex_remote", "Bonus full-remote", "flexibility", 0,
            "100% de tu jornada desde donde quieras.", 0, 0.7),
    Benefit("flex_sabbatical", "Mes sabático", "flexibility", 0,
            "Un mes pagado cada 5 años de antigüedad.", 60, 0.8),
    Benefit("flex_extra_pto", "5 días extras PTO", "flexibility", 0,
            "5 días adicionales de vacaciones pagadas.", 12, 0.7),
    Benefit("recog_bonus", "Bono performance Q", "recognition", 0,
            "Bono trimestral atado a OKRs ≥100%.", 0, 0.9),
    Benefit("recog_award", "Award peer-to-peer", "recognition", 50,
            "Reconocimiento mensual de tus pares con stipend.", 0, 0.0),
]


@dataclass(frozen=True)
class EmployeeContext:
    employee_id: int
    name: str
    department: str | None
    position: str | None
    salary: float
    tenure_months: int  # meses desde hire_date (heurística vs created_at)
    performance_score: float  # 0..1 — promedio del status de KPIs activos


@dataclass(frozen=True)
class Recommendation:
    benefit_code: str
    benefit_name: str
    category: str
    monthly_cost_eur: float
    score: float
    rationale: str


def recommend(ctx: EmployeeContext, budget_eur: float, top_n: int = 5) -> list[Recommendation]:
    """Devuelve top-N beneficios para el empleado dado un presupuesto mensual."""
    candidates = []
    for b in CATALOG:
        # Filtros duros
        if ctx.tenure_months < b.min_tenure_months:
            continue
        if ctx.performance_score < b.min_performance:
            continue
        if b.monthly_cost_eur > budget_eur:
            continue

        # Score base + bonificaciones
        score = 0.5  # base
        rationale_bits = []

        # Por categoría según contexto
        if b.category == "learning" and ctx.tenure_months < 24:
            score += 0.2
            rationale_bits.append("alto retorno en empleados con <2 años de antigüedad")
        if b.category == "wellness":
            score += 0.15
            rationale_bits.append("impacto en retención cross-sectorial")
        if b.category == "financial" and ctx.salary > 50000:
            score += 0.15
            rationale_bits.append("alineado con su banda salarial")
        if b.category == "flexibility" and ctx.performance_score >= 0.7:
            score += 0.25
            rationale_bits.append("performance arriba del target — recompensar autonomía")
        if b.category == "recognition" and ctx.performance_score >= 0.8:
            score += 0.3
            rationale_bits.append("performance superior — refuerzo de comportamiento")

        # Penalización si requiere tenure muy alta vs la del empleado
        if b.min_tenure_months > 0 and ctx.tenure_months < b.min_tenure_months * 1.2:
            score -= 0.1
            rationale_bits.append("apenas califica por antigüedad — considerar para próximo ciclo")

        # Bonus departamento
        if b.code.startswith("learn_") and ctx.department in ("Tecnologia", "Engineering", "Product"):
            score += 0.1
            rationale_bits.append("alta demanda de upskilling en su área")

        rationale = "; ".join(rationale_bits) or "beneficio elegible según perfil"
        candidates.append(Recommendation(
            benefit_code=b.code, benefit_name=b.name, category=b.category,
            monthly_cost_eur=b.monthly_cost_eur, score=round(score, 2),
            rationale=rationale,
        ))

    candidates.sort(key=lambda r: (-r.score, r.monthly_cost_eur))
    return candidates[:top_n]


def estimate_performance_score(kpi_rows: list[tuple[str, float, float]]) -> float:
    """Promedia el % de cumplimiento de N KPIs. status → score numeric.

    kpi_rows: lista de (status, actual_value, target_value).
    Si no hay KPIs → 0.5 (neutral).
    """
    if not kpi_rows:
        return 0.5
    total = 0.0
    for status, actual, target in kpi_rows:
        if target and target > 0:
            ratio = float(actual) / float(target)
            total += min(1.2, max(0.0, ratio))
        else:
            # Por status
            s_map = {"exceeded": 1.1, "met": 1.0, "on-track": 0.8, "at-risk": 0.5, "failed": 0.2}
            total += s_map.get(status, 0.5)
    return round(min(1.0, total / len(kpi_rows)), 2)


def months_since(dt: datetime | None) -> int:
    if not dt:
        return 0
    now = datetime.utcnow().replace(tzinfo=dt.tzinfo) if dt.tzinfo else datetime.utcnow()
    delta = now - dt
    return max(0, int(delta.days / 30))

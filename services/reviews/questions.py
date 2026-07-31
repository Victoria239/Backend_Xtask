"""Catálogo de preguntas para reviews 360°.

Fijo en código por ahora. Cuando RH necesite editarlos lo movemos a DB
con una vista de admin.

Cada pregunta tiene:
- code: id estable (no cambia entre ciclos)
- category: performance | collaboration | growth | leadership
- text: enunciado
- roles: qué roles de reviewer ven esta pregunta (todos si vacío)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewQuestion:
    code: str
    category: str
    text: str
    roles: tuple[str, ...] = ()  # vacío = todos


QUESTIONS: list[ReviewQuestion] = [
    # Performance
    ReviewQuestion("p_delivery", "performance",
        "¿Entrega resultados de calidad consistentemente?"),
    ReviewQuestion("p_ownership", "performance",
        "¿Toma ownership end-to-end de sus responsabilidades?"),
    ReviewQuestion("p_quality", "performance",
        "¿La calidad de su trabajo está a la altura del rol?"),
    # Collaboration
    ReviewQuestion("c_team", "collaboration",
        "¿Colabora efectivamente con su equipo?"),
    ReviewQuestion("c_communication", "collaboration",
        "¿Se comunica de forma clara, oportuna y respetuosa?"),
    ReviewQuestion("c_feedback", "collaboration",
        "¿Da y recibe feedback con apertura?"),
    # Growth
    ReviewQuestion("g_learning", "growth",
        "¿Invierte en su desarrollo profesional activamente?"),
    ReviewQuestion("g_adaptability", "growth",
        "¿Se adapta a cambios y aprende de errores?"),
    # Leadership (solo para roles manager y self/manager)
    ReviewQuestion("l_vision", "leadership",
        "¿Comunica una visión clara y inspira al equipo?",
        roles=("self", "manager", "report")),
    ReviewQuestion("l_decisions", "leadership",
        "¿Toma decisiones difíciles cuando hace falta?",
        roles=("self", "manager", "report")),
]


def questions_for_role(role: str) -> list[ReviewQuestion]:
    return [q for q in QUESTIONS if not q.roles or role in q.roles]


CATEGORIES = ["performance", "collaboration", "growth", "leadership"]
ROLES = ["self", "manager", "peer", "report"]

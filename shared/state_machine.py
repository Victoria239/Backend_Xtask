"""State Pattern — Declarative state machines for entity lifecycles.

Defines allowed transitions for each entity type so invalid status
changes are caught before hitting the database.

Usage:
    machine = PROJECT_STATES
    machine.validate_transition("active", "paused")    # OK
    machine.validate_transition("completed", "active")  # raises ValidationException
    machine.get_allowed("active")                       # ["paused", "completed", "cancelled"]
"""

from shared.exceptions import ValidationException


class StateMachine:
    """Generic state machine that enforces allowed transitions."""

    def __init__(self, name: str, transitions: dict[str, list[str]]):
        self._name = name
        self._transitions = transitions

    @property
    def states(self) -> list[str]:
        """All known states."""
        return list(self._transitions.keys())

    def get_allowed(self, current_status: str) -> list[str]:
        """Return the list of states reachable from current_status."""
        return list(self._transitions.get(current_status, []))

    def validate_transition(self, current_status: str, new_status: str) -> None:
        """Raise ValidationException if the transition is not allowed."""
        allowed = self.get_allowed(current_status)
        if new_status not in allowed:
            raise ValidationException(
                f"[{self._name}] Cannot transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {allowed}"
            )


# ─── Concrete state machines ──────────────────────────────────────

PROJECT_STATES = StateMachine("Project", {
    "active":    ["paused", "completed", "cancelled"],
    "paused":    ["active", "cancelled"],
    "completed": ["archived"],
    "cancelled": ["archived"],
    "archived":  [],
})

PAYROLL_STATES = StateMachine("Payroll", {
    "pending":   ["approved", "rejected"],
    "approved":  ["paid", "pending"],
    "rejected":  ["pending"],
    "paid":      [],
})

INVOICE_STATES = StateMachine("Invoice", {
    "pending":   ["sent", "cancelled"],
    "sent":      ["paid", "overdue", "cancelled"],
    "paid":      [],
    "overdue":   ["paid", "cancelled"],
    "cancelled": [],
})

BUDGET_STATES = StateMachine("Budget", {
    "active":    ["frozen", "closed"],
    "frozen":    ["active", "closed"],
    "closed":    [],
})

KPI_STATES = StateMachine("KPI", {
    "pending":      ["in_progress"],
    "in_progress":  ["achieved", "not_achieved"],
    "achieved":     [],
    "not_achieved": ["in_progress"],
})

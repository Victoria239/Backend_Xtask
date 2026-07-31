"""Tests para la state machine de contratos (E-02).

ALLOWED_TRANSITIONS:
    draft     → {review, cancelled}
    review    → {signed, draft, cancelled}
    signed    → {expired, cancelled}
    expired   → {}   (terminal)
    cancelled → {}   (terminal)

Estos tests fijan ese contrato: si alguien lo cambia sin actualizar el test,
queda explícito en el diff.
"""

import pytest

from services.contracts.service import ALLOWED_TRANSITIONS


class TestAllowedTransitions:
    def test_draft_can_become_review_or_cancelled(self):
        assert ALLOWED_TRANSITIONS["draft"] == {"review", "cancelled"}

    def test_review_can_become_signed_or_back_to_draft(self):
        assert ALLOWED_TRANSITIONS["review"] == {"signed", "draft", "cancelled"}

    def test_signed_can_only_expire_or_cancel(self):
        assert ALLOWED_TRANSITIONS["signed"] == {"expired", "cancelled"}

    def test_expired_is_terminal(self):
        assert ALLOWED_TRANSITIONS["expired"] == set()

    def test_cancelled_is_terminal(self):
        assert ALLOWED_TRANSITIONS["cancelled"] == set()


class TestIllegalTransitions:
    """Algunas que NO deben estar permitidas — atrapan regresiones."""

    def test_cannot_skip_review(self):
        """draft → signed sin pasar por review es regresión clásica."""
        assert "signed" not in ALLOWED_TRANSITIONS["draft"]

    def test_cannot_resurrect_expired(self):
        """expired no puede volver a draft."""
        assert "draft" not in ALLOWED_TRANSITIONS["expired"]
        assert "signed" not in ALLOWED_TRANSITIONS["expired"]

    def test_cannot_resurrect_cancelled(self):
        assert "draft" not in ALLOWED_TRANSITIONS["cancelled"]
        assert "review" not in ALLOWED_TRANSITIONS["cancelled"]

    def test_cannot_unsign(self):
        """signed no puede volver a review."""
        assert "review" not in ALLOWED_TRANSITIONS["signed"]
        assert "draft" not in ALLOWED_TRANSITIONS["signed"]


class TestStateMachineCoverage:
    """Toda transición posible debe ser legal o ilegal explícitamente — nada raro."""

    KNOWN_STATES = {"draft", "review", "signed", "expired", "cancelled"}

    def test_all_states_have_entry(self):
        assert set(ALLOWED_TRANSITIONS.keys()) == self.KNOWN_STATES

    @pytest.mark.parametrize("state", ["draft", "review", "signed", "expired", "cancelled"])
    def test_no_state_can_transition_to_itself(self, state):
        """Self-loop sería sospechoso (¿por qué transicionar?). Atrápalo."""
        assert state not in ALLOWED_TRANSITIONS[state]

    @pytest.mark.parametrize("state", ["draft", "review", "signed", "expired", "cancelled"])
    def test_no_transition_targets_unknown_state(self, state):
        """Una transición a un estado desconocido es bug — el frontend no sabría qué hacer."""
        targets = ALLOWED_TRANSITIONS[state]
        unknown = targets - self.KNOWN_STATES
        assert unknown == set(), f"{state} transitions to unknown states: {unknown}"

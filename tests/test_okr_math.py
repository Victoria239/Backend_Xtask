"""Tests para la matemática de cascada y semáforo de OKRs (C-02).

Cubrimos los puntos de inflexión del semáforo y los casos límite que la regla
documentada en docs/piloto/04_okrs_y_kpis.md promete.
"""

from dataclasses import dataclass

from services.okrs.service import _kr_progress, _status_from_progress


@dataclass
class FakeKR:
    """Estructura mínima de KR para no depender del modelo SQLAlchemy."""
    baseline: float
    target: float
    current: float


class TestStatusFromProgress:
    """Boundaries del semáforo según las constantes en service.py."""

    def test_exceeded(self):
        assert _status_from_progress(150) == "exceeded"
        assert _status_from_progress(120) == "exceeded"

    def test_met_boundary(self):
        assert _status_from_progress(100) == "met"
        assert _status_from_progress(119.99) == "met"

    def test_on_track_boundary(self):
        assert _status_from_progress(99.99) == "on-track"
        assert _status_from_progress(70) == "on-track"

    def test_at_risk_boundary(self):
        assert _status_from_progress(69.99) == "at-risk"
        assert _status_from_progress(40) == "at-risk"

    def test_off_track_boundary(self):
        assert _status_from_progress(39.99) == "off-track"
        assert _status_from_progress(0) == "off-track"
        assert _status_from_progress(-5) == "off-track"


class TestKRProgress:
    """Cálculo de progreso por KR — verificamos linealidad y caps."""

    def test_at_target_is_100(self):
        kr = FakeKR(baseline=0, target=10, current=10)
        assert _kr_progress(kr) == 100.0

    def test_at_baseline_is_0(self):
        kr = FakeKR(baseline=0, target=10, current=0)
        assert _kr_progress(kr) == 0.0

    def test_halfway(self):
        kr = FakeKR(baseline=0, target=100, current=50)
        assert _kr_progress(kr) == 50.0

    def test_with_nonzero_baseline(self):
        # Baseline=50, target=150 → range 100. current=100 → 50% completado del delta
        kr = FakeKR(baseline=50, target=150, current=100)
        assert _kr_progress(kr) == 50.0

    def test_above_target_capped_at_150(self):
        kr = FakeKR(baseline=0, target=10, current=1000)
        # Sin cap sería 10000%; debe estar en 150 para evitar volar el dashboard
        assert _kr_progress(kr) == 150.0

    def test_below_baseline_floors_at_0(self):
        kr = FakeKR(baseline=10, target=20, current=5)
        # Sin floor sería -50%; debe estar en 0
        assert _kr_progress(kr) == 0.0

    def test_target_equals_baseline_completed(self):
        """Edge case: target == baseline → no hay rango. Si current >= target, 100%."""
        kr = FakeKR(baseline=10, target=10, current=15)
        assert _kr_progress(kr) == 100.0

    def test_target_equals_baseline_not_completed(self):
        kr = FakeKR(baseline=10, target=10, current=5)
        assert _kr_progress(kr) == 0.0


class TestEndToEndScenarios:
    """Casos reales del piloto."""

    def test_features_kr_at_80pct_is_on_track(self):
        """KR Features lanzadas: target 10, current 8 → 80% → on-track."""
        kr = FakeKR(baseline=0, target=10, current=8)
        pct = _kr_progress(kr)
        assert pct == 80.0
        assert _status_from_progress(pct) == "on-track"

    def test_sales_kr_exceeded_caps_at_120(self):
        """KR Sales: target 100k, current 130k → 130% → exceeded."""
        kr = FakeKR(baseline=0, target=100000, current=130000)
        pct = _kr_progress(kr)
        assert pct == 130.0
        assert _status_from_progress(pct) == "exceeded"

    def test_dropping_to_40pct_triggers_at_risk(self):
        """KR cae de 80% a 40% — debería cruzar a 'at-risk'."""
        kr = FakeKR(baseline=0, target=10, current=4)
        assert _kr_progress(kr) == 40.0
        assert _status_from_progress(40.0) == "at-risk"

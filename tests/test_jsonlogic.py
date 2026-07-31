"""Tests del motor JSONLogic (services/plans/jsonlogic.py).

Cubre los operadores que el constructor de planes de comisión usa en producción.
Es pure logic → no requiere DB ni containers running.
"""

import pytest

from services.plans.jsonlogic import JsonLogicError, evaluate


class TestLiterals:
    def test_literal_int(self):
        assert evaluate(5, {}) == 5

    def test_literal_string(self):
        assert evaluate("hola", {}) == "hola"

    def test_literal_list(self):
        assert evaluate([1, 2, 3], {}) == [1, 2, 3]

    def test_literal_none(self):
        assert evaluate(None, {}) is None


class TestVar:
    def test_var_simple(self):
        assert evaluate({"var": "sales"}, {"sales": 100}) == 100

    def test_var_missing_returns_none(self):
        assert evaluate({"var": "missing"}, {}) is None

    def test_var_with_default(self):
        assert evaluate({"var": ["missing", 0]}, {}) == 0

    def test_var_nested(self):
        assert evaluate({"var": "employee.salary"}, {"employee": {"salary": 48000}}) == 48000

    def test_var_empty_returns_full_data(self):
        data = {"sales": 100, "target": 200}
        assert evaluate({"var": ""}, data) == data


class TestComparison:
    def test_gte_true(self):
        assert evaluate({">=": [100, 50]}, {}) is True

    def test_gte_false(self):
        assert evaluate({">=": [10, 50]}, {}) is False

    def test_gte_equal(self):
        assert evaluate({">=": [50, 50]}, {}) is True

    def test_lt_with_var(self):
        assert evaluate({"<": [{"var": "sales"}, 100]}, {"sales": 50}) is True

    def test_eq_strict_types(self):
        # JSONLogic minimal: == y === se comportan igual (sin coerción JS)
        assert evaluate({"==": [5, 5]}, {}) is True
        assert evaluate({"==": ["5", 5]}, {}) is False  # tipos distintos

    def test_neq(self):
        assert evaluate({"!=": [5, 6]}, {}) is True


class TestArithmetic:
    def test_add(self):
        assert evaluate({"+": [1, 2, 3]}, {}) == 6

    def test_subtract_binary(self):
        assert evaluate({"-": [10, 3]}, {}) == 7

    def test_subtract_unary_negates(self):
        assert evaluate({"-": [5]}, {}) == -5

    def test_multiply(self):
        assert evaluate({"*": [{"var": "sales"}, 0.05]}, {"sales": 80000}) == 4000.0

    def test_divide(self):
        assert evaluate({"/": [10, 2]}, {}) == 5.0

    def test_divide_by_zero_raises(self):
        with pytest.raises(JsonLogicError, match="ero"):
            evaluate({"/": [10, 0]}, {})

    def test_min(self):
        assert evaluate({"min": [10, 5, 20]}, {}) == 5

    def test_max(self):
        assert evaluate({"max": [10, 5, 20]}, {}) == 20


class TestLogic:
    def test_and_both_truthy(self):
        # `and` devuelve el último truthy, no necesariamente True
        assert evaluate({"and": [True, True]}, {}) is True

    def test_and_short_circuits(self):
        assert evaluate({"and": [False, True]}, {}) is False

    def test_or_returns_first_truthy(self):
        assert evaluate({"or": [False, "hello", True]}, {}) == "hello"

    def test_not(self):
        assert evaluate({"not": [True]}, {}) is False
        assert evaluate({"!": [False]}, {}) is True


class TestIf:
    def test_if_ternary_true(self):
        assert evaluate({"if": [True, "yes", "no"]}, {}) == "yes"

    def test_if_ternary_false(self):
        assert evaluate({"if": [False, "yes", "no"]}, {}) == "no"

    def test_if_n_ary(self):
        # if [cond1, val1, cond2, val2, else]
        rule = {"if": [
            {"<": [{"var": "sales"}, 100]}, "small",
            {"<": [{"var": "sales"}, 1000]}, "medium",
            "large",
        ]}
        assert evaluate(rule, {"sales": 50}) == "small"
        assert evaluate(rule, {"sales": 500}) == "medium"
        assert evaluate(rule, {"sales": 5000}) == "large"


class TestErrors:
    def test_unknown_op_raises(self):
        with pytest.raises(JsonLogicError, match="no soportado"):
            evaluate({"foo": []}, {})

    def test_multiple_keys_raises(self):
        with pytest.raises(JsonLogicError, match="exactamente 1"):
            evaluate({"+": [1], "-": [1]}, {})


class TestCommissionPlanScenarios:
    """Casos reales de planes de comisión que debe poder calcular."""

    def test_tiered_plan_tier_1(self):
        """Sales=30k, esperado 30000*0.02 = 600."""
        rule_when = {"<": [{"var": "sales"}, 50000]}
        rule_amount = {"*": [{"var": "sales"}, 0.02]}
        ctx = {"sales": 30000}
        assert evaluate(rule_when, ctx) is True
        assert evaluate(rule_amount, ctx) == 600.0

    def test_tiered_plan_tier_3_with_bonus(self):
        """Sales=200k, esperado 200000*0.08 + 500 = 16500."""
        rule_when = {">=": [{"var": "sales"}, 150000]}
        rule_amount = {"+": [{"*": [{"var": "sales"}, 0.08]}, 500]}
        ctx = {"sales": 200000}
        assert evaluate(rule_when, ctx) is True
        assert evaluate(rule_amount, ctx) == 16500.0

    def test_compound_senior_bonus(self):
        """Sólo paga el plus si is_senior=True y sales > 50k."""
        rule = {"if": [
            {"and": [
                {">": [{"var": "sales"}, 50000]},
                {"var": "is_senior"},
            ]},
            {"+": [{"*": [{"var": "sales"}, 0.06]}, 1000]},
            0,
        ]}
        assert evaluate(rule, {"sales": 75000, "is_senior": True}) == 5500.0
        assert evaluate(rule, {"sales": 75000, "is_senior": False}) == 0
        assert evaluate(rule, {"sales": 30000, "is_senior": True}) == 0

    def test_margin_based(self):
        """Comisión solo si margin > 30%."""
        rule_when = {">": [{"var": "margin_pct"}, 0.3]}
        assert evaluate(rule_when, {"margin_pct": 0.4}) is True
        assert evaluate(rule_when, {"margin_pct": 0.25}) is False

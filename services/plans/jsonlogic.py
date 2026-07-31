"""Minimal JSONLogic evaluator para el motor de comisiones (C-03 / ADR-015).

Soporta los operadores que necesitamos para reglas de comisión:
- Lógicos: and, or, not, !!
- Comparación: ==, ===, !=, !==, >, <, >=, <=
- Aritméticos: +, -, *, /, %, min, max
- Control: if (ternario o N-ario)
- Referencias: var (con default opcional)
- Strings: in, cat
- Arrays: in

No implementamos `missing`, `map`, `reduce` ni `merge` — fuera del alcance MVP.

Diseño: el evaluador no lanza si encuentra una clave desconocida (devuelve None)
porque queremos que el constructor visual sea forgiving. Las validaciones serias
las hace el frontend antes de persistir.
"""

from typing import Any


class JsonLogicError(ValueError):
    """Error explícito al evaluar — distinguible de TypeError o KeyError genéricos."""


def _resolve_var(path: str, data: dict[str, Any], default: Any = None) -> Any:
    if path == "" or path is None:
        return data
    parts = str(path).split(".")
    cur: Any = data
    for p in parts:
        if isinstance(cur, dict):
            if p not in cur:
                return default
            cur = cur[p]
        elif isinstance(cur, list):
            try:
                idx = int(p)
                cur = cur[idx]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return cur


def _truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return len(v) > 0
    if isinstance(v, (list, dict)):
        return len(v) > 0
    return bool(v)


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def evaluate(rule: Any, data: dict[str, Any]) -> Any:
    """Evalúa una expresión JSONLogic contra `data`.

    Si `rule` no es dict, se devuelve tal cual (literal).
    Si es dict con una sola clave, se trata como operador.
    """
    if not isinstance(rule, dict):
        return rule
    if len(rule) != 1:
        raise JsonLogicError(f"Una regla debe tener exactamente 1 operador, vino: {list(rule.keys())}")

    op, args = next(iter(rule.items()))

    # Var puede tener distintos shapes
    if op == "var":
        if not isinstance(args, list):
            return _resolve_var(args, data) if args is not None else data
        path = args[0] if len(args) > 0 else None
        default = args[1] if len(args) > 1 else None
        return _resolve_var(path, data, default)

    # Para el resto: si args no es list, lo envolvemos
    if not isinstance(args, list):
        args = [args]
    evaluated = [evaluate(a, data) for a in args]

    if op in ("==", "==="):
        return evaluated[0] == evaluated[1]
    if op in ("!=", "!=="):
        return evaluated[0] != evaluated[1]
    if op == ">":
        return _num(evaluated[0]) > _num(evaluated[1])
    if op == "<":
        return _num(evaluated[0]) < _num(evaluated[1])
    if op == ">=":
        return _num(evaluated[0]) >= _num(evaluated[1])
    if op == "<=":
        return _num(evaluated[0]) <= _num(evaluated[1])

    if op == "and":
        result: Any = True
        for v in evaluated:
            if not _truthy(v):
                return v
            result = v
        return result
    if op == "or":
        for v in evaluated:
            if _truthy(v):
                return v
        return evaluated[-1] if evaluated else False
    if op == "not" or op == "!":
        return not _truthy(evaluated[0])
    if op == "!!":
        return _truthy(evaluated[0])

    if op == "+":
        return sum(_num(v) for v in evaluated)
    if op == "-":
        if len(evaluated) == 1:
            return -_num(evaluated[0])
        return _num(evaluated[0]) - sum(_num(v) for v in evaluated[1:])
    if op == "*":
        out = 1.0
        for v in evaluated:
            out *= _num(v)
        return out
    if op == "/":
        if len(evaluated) < 2:
            raise JsonLogicError("/ requiere ≥2 operandos")
        denom = _num(evaluated[1])
        if denom == 0:
            raise JsonLogicError("División por cero")
        return _num(evaluated[0]) / denom
    if op == "%":
        if len(evaluated) < 2 or _num(evaluated[1]) == 0:
            raise JsonLogicError("% requiere ≥2 operandos no-cero")
        return _num(evaluated[0]) % _num(evaluated[1])
    if op == "min":
        return min(_num(v) for v in evaluated)
    if op == "max":
        return max(_num(v) for v in evaluated)

    if op == "if":
        # if [cond, then, cond2, then2, ..., else]
        # Forma ternaria estándar: if [cond, then, else]
        i = 0
        while i + 1 < len(evaluated):
            if _truthy(evaluated[i]):
                return evaluated[i + 1]
            i += 2
        if i < len(evaluated):
            return evaluated[i]
        return None

    if op == "in":
        needle, haystack = evaluated[0], evaluated[1]
        if isinstance(haystack, (list, str)):
            return needle in haystack
        return False
    if op == "cat":
        return "".join(str(v) for v in evaluated if v is not None)

    raise JsonLogicError(f"Operador no soportado: {op!r}")

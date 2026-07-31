"""Motor de forecasting puro (AI-04).

Diseño:
- Sin dependencias pesadas (statsmodels/sklearn). Usamos numpy para regresión
  lineal y banda de confianza vía residuos.
- Soporta tres modos:
    * linear: regresión lineal sobre el tiempo (default cuando hay 3+ puntos).
    * holt: suavizado exponencial doble (cuando hay 5+ puntos con tendencia clara).
    * naive: si hay <3 puntos, extrapolamos linealmente entre baseline y target.

Entrada: lista de tuplas (timestamp, value).
Salida: forecast con timestamps + value + ic_low + ic_high.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import numpy as np

ForecastMethod = Literal["linear", "holt", "naive"]


@dataclass(frozen=True)
class ForecastPoint:
    t: datetime
    value: float
    ic_low: float
    ic_high: float


@dataclass(frozen=True)
class ForecastResult:
    method: ForecastMethod
    points: list[ForecastPoint]
    r2: float | None  # coeficiente de determinación (linear only)
    last_observed_at: datetime | None
    last_observed_value: float | None


def _linear_forecast(
    timestamps: list[datetime], values: list[float], horizon: int, freq_days: float,
) -> ForecastResult:
    """Regresión lineal y(t) = a + b*t. IC ±1.96*sigma_residuo."""
    t0 = timestamps[0]
    xs = np.array([(t - t0).total_seconds() / 86400 for t in timestamps], dtype=float)
    ys = np.array(values, dtype=float)
    if len(xs) < 2:
        # Defensa: nunca debería llegar acá si hay >= 3 puntos pero por las dudas
        return _naive_forecast(timestamps, values, horizon, freq_days)

    # polyfit grado 1
    coeffs = np.polyfit(xs, ys, 1)
    slope, intercept = float(coeffs[0]), float(coeffs[1])
    predicted = slope * xs + intercept
    residuals = ys - predicted
    sigma = float(residuals.std(ddof=1)) if len(xs) > 2 else float(abs(residuals).mean())
    if sigma == 0:
        sigma = max(0.01 * abs(intercept), 0.01)

    ss_res = float((residuals**2).sum())
    ss_tot = float(((ys - ys.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None

    last_t = timestamps[-1]
    last_x = (last_t - t0).total_seconds() / 86400

    points = []
    for i in range(1, horizon + 1):
        t_offset = last_x + i * freq_days
        ts = t0 + timedelta(days=t_offset)
        y_pred = slope * t_offset + intercept
        # IC crece con el horizonte (sigma * sqrt(1 + 1/n + (x-mean)^2/Sxx))
        # Aproximación simple: ic = 1.96 * sigma * sqrt(1 + i/n)
        n = len(xs)
        ic_factor = 1.96 * sigma * math.sqrt(1 + i / n)
        points.append(ForecastPoint(
            t=ts, value=float(y_pred),
            ic_low=float(y_pred - ic_factor),
            ic_high=float(y_pred + ic_factor),
        ))

    return ForecastResult(
        method="linear", points=points, r2=r2,
        last_observed_at=last_t, last_observed_value=float(values[-1]),
    )


def _holt_forecast(
    timestamps: list[datetime], values: list[float], horizon: int, freq_days: float,
) -> ForecastResult:
    """Holt's linear (exponential smoothing con tendencia).

    L_t = alpha * y_t + (1 - alpha) * (L_{t-1} + T_{t-1})
    T_t = beta * (L_t - L_{t-1}) + (1 - beta) * T_{t-1}
    forecast_{t+h} = L_t + h * T_t

    Buscamos alpha, beta por grid search (suficiente para MVP).
    """
    ys = np.array(values, dtype=float)
    n = len(ys)
    best = None
    grid = np.linspace(0.1, 0.9, 9)
    for alpha in grid:
        for beta in grid:
            L = ys[0]
            T = ys[1] - ys[0]
            sse = 0.0
            for i in range(1, n):
                Lnew = alpha * ys[i] + (1 - alpha) * (L + T)
                Tnew = beta * (Lnew - L) + (1 - beta) * T
                # forecast del paso siguiente vs. valor real
                pred = L + T
                sse += (ys[i] - pred) ** 2
                L, T = Lnew, Tnew
        if best is None or sse < best[0]:
            best = (sse, float(alpha), float(beta), float(L), float(T))

    assert best is not None
    sse, alpha_opt, beta_opt, L_final, T_final = best
    sigma = math.sqrt(sse / max(n - 2, 1))

    last_t = timestamps[-1]
    points = []
    for i in range(1, horizon + 1):
        ts = last_t + timedelta(days=i * freq_days)
        y_pred = L_final + i * T_final
        ic_factor = 1.96 * sigma * math.sqrt(i)  # IC crece con el horizonte
        points.append(ForecastPoint(
            t=ts, value=y_pred, ic_low=y_pred - ic_factor, ic_high=y_pred + ic_factor,
        ))

    return ForecastResult(
        method="holt", points=points, r2=None,
        last_observed_at=last_t, last_observed_value=float(values[-1]),
    )


def _naive_forecast(
    timestamps: list[datetime], values: list[float], horizon: int, freq_days: float,
) -> ForecastResult:
    """Extrapolación naive cuando hay <3 datos: usamos la pendiente del último intervalo."""
    if len(values) >= 2:
        last_t = timestamps[-1]
        slope_per_day = (values[-1] - values[-2]) / max(
            (timestamps[-1] - timestamps[-2]).total_seconds() / 86400, 1,
        )
        sigma = abs(values[-1] - values[-2]) * 0.5
    elif len(values) == 1:
        last_t = timestamps[-1] if timestamps else datetime.utcnow()
        slope_per_day = 0
        sigma = abs(values[-1]) * 0.1 if values else 1
    else:
        return ForecastResult(
            method="naive", points=[], r2=None,
            last_observed_at=None, last_observed_value=None,
        )

    last_v = values[-1] if values else 0
    points = []
    for i in range(1, horizon + 1):
        ts = last_t + timedelta(days=i * freq_days)
        y_pred = last_v + slope_per_day * i * freq_days
        ic_factor = sigma * math.sqrt(i)
        points.append(ForecastPoint(
            t=ts, value=float(y_pred),
            ic_low=float(y_pred - ic_factor),
            ic_high=float(y_pred + ic_factor),
        ))

    return ForecastResult(
        method="naive", points=points, r2=None,
        last_observed_at=last_t, last_observed_value=float(last_v),
    )


def forecast_series(
    timestamps: list[datetime],
    values: list[float],
    horizon: int = 6,
    freq_days: float = 30.0,
    method: ForecastMethod | None = None,
) -> ForecastResult:
    """Public API. Si method=None elige automáticamente:
       - <3 puntos → naive
       - 3-4 puntos → linear
       - 5+ puntos → holt (mejor con tendencia)
    """
    if len(timestamps) != len(values):
        raise ValueError("timestamps y values deben tener la misma longitud")
    if horizon <= 0:
        raise ValueError("horizon debe ser > 0")

    if method is None:
        if len(values) >= 5:
            method = "holt"
        elif len(values) >= 3:
            method = "linear"
        else:
            method = "naive"

    if method == "linear":
        return _linear_forecast(timestamps, values, horizon, freq_days)
    if method == "holt":
        return _holt_forecast(timestamps, values, horizon, freq_days)
    return _naive_forecast(timestamps, values, horizon, freq_days)

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from macropulse.models.baseline import ForecastResult


def empirical_interval_half_width(
    prior_results: pd.DataFrame,
    model_name: str,
    forecast_stage: str,
    coverage: float = 0.80,
    window: int = 20,
    min_history: int = 12,
) -> tuple[float | None, dict]:
    if not 0 < coverage < 1:
        raise ValueError("coverage must be between zero and one.")
    diagnostics = {
        "method": "model_interval_fallback",
        "coverage": float(coverage),
        "window": int(window),
        "min_history": int(min_history),
        "history_count": 0,
        "max_prior_forecast_date": None,
    }
    if prior_results.empty:
        return None, diagnostics

    required = {"model_name", "forecast_stage", "forecast_date", "point_forecast", "actual"}
    if required.difference(prior_results.columns):
        return None, diagnostics

    frame = prior_results.loc[
        (prior_results["model_name"] == model_name)
        & (prior_results["forecast_stage"] == forecast_stage)
    ].dropna(subset=["point_forecast", "actual"]).copy()
    if frame.empty:
        return None, diagnostics
    frame["forecast_date"] = pd.to_datetime(frame["forecast_date"])
    frame = frame.sort_values("forecast_date")
    if window > 0:
        frame = frame.tail(window)
    diagnostics["history_count"] = int(len(frame))
    diagnostics["max_prior_forecast_date"] = frame["forecast_date"].max().date().isoformat()
    if len(frame) < min_history:
        return None, diagnostics

    errors = (frame["point_forecast"] - frame["actual"]).abs().to_numpy(dtype=float)
    errors = errors[np.isfinite(errors)]
    if errors.size < min_history:
        return None, diagnostics
    try:
        width = float(np.quantile(errors, coverage, method="higher"))
    except TypeError:  # NumPy < 1.22 compatibility
        width = float(np.quantile(errors, coverage, interpolation="higher"))
    if not np.isfinite(width) or width <= 0:
        return None, diagnostics
    diagnostics.update({"method": "rolling_empirical_absolute_error", "half_width": width})
    return width, diagnostics


def calibrate_forecast_interval(
    result: ForecastResult,
    prior_results: pd.DataFrame,
    forecast_stage: str,
    coverage: float = 0.80,
    window: int = 20,
    min_history: int = 12,
) -> tuple[ForecastResult, dict]:
    width, diagnostics = empirical_interval_half_width(
        prior_results=prior_results,
        model_name=result.model_name,
        forecast_stage=forecast_stage,
        coverage=coverage,
        window=window,
        min_history=min_history,
    )
    diagnostics["raw_lower"] = float(result.lower)
    diagnostics["raw_upper"] = float(result.upper)
    if width is None:
        diagnostics["calibrated_lower"] = float(result.lower)
        diagnostics["calibrated_upper"] = float(result.upper)
        return result, diagnostics

    calibrated = replace(
        result,
        lower=float(result.point_forecast - width),
        upper=float(result.point_forecast + width),
        diagnostics={**result.diagnostics, "interval_calibration": diagnostics},
    )
    diagnostics["calibrated_lower"] = calibrated.lower
    diagnostics["calibrated_upper"] = calibrated.upper
    return calibrated, diagnostics

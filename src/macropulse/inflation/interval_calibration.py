from __future__ import annotations

import json
import math
import uuid

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import get_inflation_model_config
from macropulse.inflation.versioning import current_inflation_model_identity


METHOD = "prior_only_rolling_absolute_error_quantile"


def _higher_quantile(values: np.ndarray, probability: float) -> float:
    """Return a deterministic finite-sample empirical quantile.

    The probability uses the standard conformal finite-sample adjustment
    ceil((n + 1) * coverage) / n and the conservative ``higher`` order statistic.
    """
    if values.size == 0:
        raise ValueError("At least one calibration error is required.")
    probability = min(1.0, max(0.0, float(probability)))
    try:
        return float(np.quantile(values, probability, method="higher"))
    except TypeError:  # NumPy < 1.22 compatibility
        return float(np.quantile(values, probability, interpolation="higher"))


def conformal_half_width(
    prior_absolute_errors: pd.Series | np.ndarray | list[float],
    coverage: float,
) -> float:
    clean = pd.to_numeric(pd.Series(prior_absolute_errors), errors="coerce").dropna()
    clean = clean.loc[clean >= 0].astype(float)
    if clean.empty:
        raise ValueError("No valid prior absolute forecast errors are available.")
    n = len(clean)
    probability = min(1.0, math.ceil((n + 1) * float(coverage)) / n)
    return _higher_quantile(clean.to_numpy(), probability)


def calibrate_interval_frame(
    results: pd.DataFrame,
    calibration_id: str,
    coverage: float = 0.80,
    minimum_prior_errors: int = 24,
    rolling_window: int = 48,
    created_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Calibrate intervals from strictly prior pseudo-real-time forecast errors.

    Point forecasts and actuals are not changed. Each target/stage/model group is
    processed in target-month order. The current month's error is appended only
    after its interval has been constructed, preventing look-ahead leakage.
    """
    required = {
        "backtest_id",
        "target_series",
        "forecast_stage",
        "target_period",
        "model_name",
        "point_forecast",
        "actual",
        "abs_error",
    }
    missing = sorted(required.difference(results.columns))
    if missing:
        raise ValueError(f"Backtest results are missing required columns: {missing}")
    if not 0.0 < coverage < 1.0:
        raise ValueError("coverage must be between zero and one.")
    if minimum_prior_errors < 12:
        raise ValueError("minimum_prior_errors must be at least 12.")
    if rolling_window < minimum_prior_errors:
        raise ValueError("rolling_window cannot be smaller than minimum_prior_errors.")

    timestamp = created_at or pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows: list[dict] = []
    group_columns = ["target_series", "forecast_stage", "model_name"]
    ordered = results.copy()
    ordered["_period"] = pd.PeriodIndex(ordered["target_period"], freq="M")
    ordered = ordered.sort_values(group_columns + ["_period"])

    for keys, group in ordered.groupby(group_columns, sort=True):
        target_series, forecast_stage, model_name = keys
        prior: list[tuple[pd.Period, float]] = []
        for _, row in group.iterrows():
            target_period = row["_period"]
            available = prior[-rolling_window:]
            prior_count = len(prior)
            window_count = len(available)
            cutoff = str(available[-1][0]) if available else None
            if window_count >= minimum_prior_errors:
                width = conformal_half_width(
                    [error for _, error in available], coverage=coverage
                )
                lower = float(row["point_forecast"]) - width
                upper = float(row["point_forecast"]) + width
                covered: bool | None = bool(
                    lower <= float(row["actual"]) <= upper
                )
                status = "calibrated"
            else:
                width = np.nan
                lower = np.nan
                upper = np.nan
                covered = None
                status = "warmup"

            rows.append(
                {
                    "calibration_id": calibration_id,
                    "backtest_id": str(row["backtest_id"]),
                    "target_series": str(target_series),
                    "forecast_stage": str(forecast_stage),
                    "target_period": str(target_period),
                    "model_name": str(model_name),
                    "lower_80": lower,
                    "upper_80": upper,
                    "interval_covered": covered,
                    "interval_half_width": width,
                    "prior_error_count": prior_count,
                    "calibration_window_count": window_count,
                    "calibration_cutoff_period": cutoff,
                    "calibration_status": status,
                    "created_at": timestamp,
                }
            )
            error = float(row["abs_error"])
            if np.isfinite(error):
                prior.append((target_period, error))

    return pd.DataFrame(rows)


def _coverage_metrics(calibrated: pd.DataFrame) -> dict:
    usable = calibrated.loc[calibrated["calibration_status"] == "calibrated"].copy()
    if usable.empty:
        return {}
    payload: dict[str, dict] = {}
    for (target, stage, model), frame in usable.groupby(
        ["target_series", "forecast_stage", "model_name"]
    ):
        payload.setdefault(str(target), {}).setdefault(str(stage), {})[str(model)] = {
            "observations": int(len(frame)),
            "coverage": float(pd.to_numeric(frame["interval_covered"]).mean()),
            "average_half_width": float(frame["interval_half_width"].mean()),
            "minimum_prior_errors": int(frame["prior_error_count"].min()),
        }
    return payload


def run_prior_only_interval_calibration(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    coverage: float | None = None,
    minimum_prior_errors: int | None = None,
    rolling_window: int | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    config = get_inflation_model_config()
    identity = current_inflation_model_identity()
    coverage = float(
        coverage if coverage is not None else config.get("interval_coverage", 0.80)
    )
    minimum_prior_errors = int(
        minimum_prior_errors
        if minimum_prior_errors is not None
        else config.get("interval_calibration_minimum_errors", 24)
    )
    rolling_window = int(
        rolling_window
        if rolling_window is not None
        else config.get("interval_calibration_window", 48)
    )

    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM inflation_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No inflation vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    base = repository.query_df(
        """
        SELECT *
        FROM inflation_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, model_name, target_period
        """,
        [backtest_id],
    )
    if base.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no forecasts.")

    calibration_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    calibrated = calibrate_interval_frame(
        base,
        calibration_id=calibration_id,
        coverage=coverage,
        minimum_prior_errors=minimum_prior_errors,
        rolling_window=rolling_window,
        created_at=created_at,
    )
    metrics = _coverage_metrics(calibrated)
    usable = calibrated["calibration_status"] == "calibrated"
    status = "success" if bool(usable.any()) else "insufficient_history"
    run_record = pd.DataFrame(
        [
            {
                "calibration_id": calibration_id,
                "backtest_id": backtest_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "created_at": created_at,
                "method": METHOD,
                "target_coverage": coverage,
                "minimum_prior_errors": minimum_prior_errors,
                "rolling_window": rolling_window,
                "status": status,
                "metrics_json": json.dumps(metrics, default=str),
                "notes": (
                    "Intervals are calibrated from strictly earlier target-month "
                    "pseudo-real-time absolute forecast errors. Warm-up rows retain no interval."
                ),
            }
        ]
    )
    repository.save_inflation_interval_calibration_outputs(run_record, calibrated)
    return {
        "calibration_id": calibration_id,
        "backtest_id": backtest_id,
        "status": status,
        "results": calibrated,
        "metrics": metrics,
        "coverage": coverage,
        "minimum_prior_errors": minimum_prior_errors,
        "rolling_window": rolling_window,
    }

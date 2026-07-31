from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.config import get_labour_model_config
from macropulse.labour.versioning import current_labour_model_identity


METHOD = "exp_weighted_q80"


def weighted_quantile(
    values: pd.Series | np.ndarray | list[float],
    weights: pd.Series | np.ndarray | list[float],
    probability: float,
) -> float:
    """Return a deterministic weighted empirical quantile."""
    value_series = pd.to_numeric(pd.Series(values), errors="coerce")
    weight_series = pd.to_numeric(pd.Series(weights), errors="coerce")
    frame = pd.DataFrame({"value": value_series, "weight": weight_series}).dropna()
    frame = frame.loc[(frame["value"] >= 0.0) & (frame["weight"] > 0.0)]
    if frame.empty:
        raise ValueError("No valid weighted calibration errors are available.")
    probability = float(min(1.0, max(0.0, probability)))
    frame = frame.sort_values("value", kind="mergesort")
    cumulative = frame["weight"].cumsum() / float(frame["weight"].sum())
    position = int(np.searchsorted(cumulative.to_numpy(), probability, side="left"))
    position = min(position, len(frame) - 1)
    return float(frame.iloc[position]["value"])


def interval_score(
    actual: float,
    lower: float,
    upper: float,
    coverage: float,
) -> float:
    """Central prediction-interval score; lower values are better."""
    alpha = 1.0 - float(coverage)
    if not 0.0 < alpha < 1.0:
        raise ValueError("coverage must be between zero and one.")
    score = float(upper - lower)
    if actual < lower:
        score += (2.0 / alpha) * float(lower - actual)
    elif actual > upper:
        score += (2.0 / alpha) * float(actual - upper)
    return score


def calibrate_labour_interval_frame(
    results: pd.DataFrame,
    calibration_id: str,
    coverage: float = 0.80,
    minimum_prior_errors: int = 24,
    rolling_window: int = 48,
    decay: float = 0.94,
    created_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Create intervals from strictly earlier pseudo-real-time forecast errors.

    Each target/stage/model group is processed in target-month order. The current
    target month's error is appended only after its interval has been constructed,
    so it cannot calibrate its own interval.
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
    if not 0.0 < decay <= 1.0:
        raise ValueError("decay must be in (0, 1].")

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
                errors = np.asarray([error for _, error in available], dtype=float)
                ages = np.arange(window_count - 1, -1, -1, dtype=float)
                weights = np.power(float(decay), ages)
                width = weighted_quantile(errors, weights, probability=coverage)
                point = float(row["point_forecast"])
                actual = float(row["actual"])
                lower = point - width
                upper = point + width
                covered: bool | None = bool(lower <= actual <= upper)
                score = interval_score(actual, lower, upper, coverage)
                status = "calibrated"
            else:
                width = np.nan
                lower = np.nan
                upper = np.nan
                covered = None
                score = np.nan
                status = "warmup"

            rows.append(
                {
                    "calibration_id": calibration_id,
                    "backtest_id": str(row["backtest_id"]),
                    "target_series": str(target_series),
                    "forecast_stage": str(forecast_stage),
                    "target_period": str(target_period),
                    "model_name": str(model_name),
                    "interval_method": METHOD,
                    "lower_80": lower,
                    "upper_80": upper,
                    "interval_covered": covered,
                    "interval_half_width": width,
                    "interval_score": score,
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
            "mean_interval_score": float(frame["interval_score"].mean()),
            "minimum_prior_errors": int(frame["prior_error_count"].min()),
        }
    return payload


def run_prior_only_labour_interval_calibration(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    coverage: float | None = None,
    minimum_prior_errors: int | None = None,
    rolling_window: int | None = None,
    decay: float | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    config = get_labour_model_config()
    identity = current_labour_model_identity()
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
    decay = float(
        decay if decay is not None else config.get("interval_calibration_decay", 0.94)
    )

    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM labour_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No labour vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    base = repository.query_df(
        """
        SELECT *
        FROM labour_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, model_name, target_period
        """,
        [backtest_id],
    )
    if base.empty:
        raise RuntimeError(f"Labour vintage backtest {backtest_id} contains no forecasts.")

    calibration_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    calibrated = calibrate_labour_interval_frame(
        base,
        calibration_id=calibration_id,
        coverage=coverage,
        minimum_prior_errors=minimum_prior_errors,
        rolling_window=rolling_window,
        decay=decay,
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
                "decay": decay,
                "status": status,
                "metrics_json": json.dumps(metrics, default=str),
                "notes": (
                    "Intervals use exponentially weighted absolute forecast errors from "
                    "strictly earlier target months. Warm-up rows retain no calibrated interval."
                ),
            }
        ]
    )
    repository.save_labour_interval_calibration_outputs(run_record, calibrated)
    return {
        "calibration_id": calibration_id,
        "backtest_id": backtest_id,
        "status": status,
        "results": calibrated,
        "metrics": metrics,
        "coverage": coverage,
        "minimum_prior_errors": minimum_prior_errors,
        "rolling_window": rolling_window,
        "decay": decay,
        "method": METHOD,
    }

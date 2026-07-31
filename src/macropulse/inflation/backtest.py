from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import get_inflation_model_config, target_definitions
from macropulse.inflation.dataset import build_target_dataset
from macropulse.inflation.models import combine_equal_weight, fit_ar1, fit_ridge_bridge, fit_rolling_mean
from macropulse.inflation.versioning import current_inflation_model_identity


def _metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {}
    error = frame["error"].astype(float)
    return {
        "observations": int(len(frame)),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "mae": float(np.mean(np.abs(error))),
        "bias": float(np.mean(error)),
        "median_ae": float(np.median(np.abs(error))),
        "interval_coverage": float(frame["interval_covered"].mean()),
    }


def run_chronological_inflation_backtest(
    repository: MacroRepository | None = None,
    start_date: str | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    observations = repository.latest_observations()
    config = get_inflation_model_config()
    identity = current_inflation_model_identity()
    minimum = int(config.get("minimum_training_observations", 120))
    coverage = float(config.get("interval_coverage", 0.80))
    requested_start = pd.Period(start_date or "2015-01", freq="M")
    backtest_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    rows: list[dict] = []

    for definition in target_definitions():
        dataset = build_target_dataset(observations, definition.series_id)
        for position in range(minimum, len(dataset.y)):
            period = dataset.y.index[position]
            if period < requested_start:
                continue
            train_X = dataset.X.iloc[:position]
            train_y = dataset.y.iloc[:position]
            forecast_X = dataset.X.iloc[[position]]
            actual = float(dataset.y.iloc[position])
            ridge = fit_ridge_bridge(train_X, train_y, forecast_X, float(config.get("ridge_alpha", 8.0)), coverage)
            ar1 = fit_ar1(train_y, coverage=coverage)
            mean = fit_rolling_mean(train_y, int(config.get("rolling_mean_window", 12)), coverage)
            ensemble = combine_equal_weight(ridge, ar1, train_y, coverage)
            for result in [ridge, ar1, mean, ensemble]:
                error = actual - result.point_forecast
                rows.append({
                    "backtest_id": backtest_id,
                    "target_series": definition.series_id,
                    "target_period": str(period),
                    "model_name": result.model_name,
                    "point_forecast": result.point_forecast,
                    "actual": actual,
                    "error": error,
                    "abs_error": abs(error),
                    "squared_error": error ** 2,
                    "lower_80": result.lower_80,
                    "upper_80": result.upper_80,
                    "interval_covered": bool(result.lower_80 <= actual <= result.upper_80),
                    "created_at": created_at,
                })
    results = pd.DataFrame(rows)
    summary: dict[str, dict] = {}
    if not results.empty:
        for (target, model), frame in results.groupby(["target_series", "model_name"]):
            summary.setdefault(target, {})[model] = _metrics(frame)
    run = pd.DataFrame([{
        "backtest_id": backtest_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "created_at": created_at,
        "start_period": str(requested_start),
        "status": "success",
        "method": "chronological_expanding_non_vintage",
        "metrics_json": json.dumps(summary, default=str),
        "notes": "Development baseline only. Uses latest revised data and is not pseudo-real-time.",
    }])
    repository.save_inflation_backtest_outputs(run, results)
    return {"backtest_id": backtest_id, "results": results, "metrics": summary}

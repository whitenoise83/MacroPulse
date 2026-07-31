from __future__ import annotations

import json
import uuid

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.config import get_labour_model_config, target_definitions
from macropulse.labour.dataset import build_target_dataset
from macropulse.labour.models import fit_model_suite
from macropulse.labour.versioning import current_labour_model_identity


def _metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {}
    error = pd.to_numeric(frame["error"], errors="coerce").dropna()
    return {
        "observations": int(len(error)),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "mae": float(np.mean(np.abs(error))),
        "bias": float(np.mean(error)),
        "median_ae": float(np.median(np.abs(error))),
        "p90_abs_error": float(np.quantile(np.abs(error), 0.90)),
        "max_abs_error": float(np.max(np.abs(error))),
        "directional_accuracy": float(frame["direction_correct"].mean()),
        "interval_coverage": float(frame["interval_covered"].mean()),
    }


def _direction_correct(
    transform: str,
    point_forecast: float,
    actual: float,
    previous_actual: float,
) -> bool:
    if transform == "level":
        predicted_direction = np.sign(point_forecast - previous_actual)
        actual_direction = np.sign(actual - previous_actual)
    else:
        predicted_direction = np.sign(point_forecast)
        actual_direction = np.sign(actual)
    return bool(predicted_direction == actual_direction)


def run_chronological_labour_backtest(
    repository: MacroRepository | None = None,
    start_date: str | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    observations = repository.latest_observations()
    if observations.empty:
        raise RuntimeError("No FRED observations are stored. Run download_labour_data.py first.")
    config = get_labour_model_config()
    identity = current_labour_model_identity()
    minimum = int(config.get("minimum_training_observations", 120))
    requested_start = pd.Period(start_date or "2016-01", freq="M")
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
            previous_actual = float(train_y.iloc[-1])
            models = fit_model_suite(train_X, train_y, forecast_X, config)
            for result in models:
                error = actual - result.point_forecast
                rows.append(
                    {
                        "backtest_id": backtest_id,
                        "target_series": definition.series_id,
                        "target_name": definition.name,
                        "target_unit": definition.unit,
                        "target_period": str(period),
                        "model_name": result.model_name,
                        "point_forecast": result.point_forecast,
                        "actual": actual,
                        "error": error,
                        "abs_error": abs(error),
                        "squared_error": error**2,
                        "direction_correct": _direction_correct(
                            definition.transform,
                            result.point_forecast,
                            actual,
                            previous_actual,
                        ),
                        "lower_80": result.lower_80,
                        "upper_80": result.upper_80,
                        "interval_covered": bool(
                            result.lower_80 <= actual <= result.upper_80
                        ),
                        "created_at": created_at,
                    }
                )

    results = pd.DataFrame(rows)
    summary: dict[str, dict] = {}
    if not results.empty:
        for (target, model), frame in results.groupby(["target_series", "model_name"]):
            summary.setdefault(target, {})[model] = _metrics(frame)
    run = pd.DataFrame(
        [
            {
                "backtest_id": backtest_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "created_at": created_at,
                "start_period": str(requested_start),
                "status": "success",
                "method": "chronological_expanding_latest_revised",
                "metrics_json": json.dumps(summary, default=str),
                "notes": (
                    "Development baseline only. Uses latest-revised data and full-month "
                    "features; not pseudo-real-time evidence."
                ),
            }
        ]
    )
    repository.save_labour_backtest_outputs(run, results)
    return {"backtest_id": backtest_id, "results": results, "metrics": summary}

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pandas as pd

from macropulse.config import get_series_definitions, load_registry
from macropulse.data.repository import MacroRepository
from macropulse.models.baseline import (
    combine_equal_weight,
    fit_ar1,
    fit_bridge_ridge,
)
from macropulse.processing.dataset import build_bridge_dataset


def run_baseline_nowcast(repository: MacroRepository | None = None) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()

    registry = load_registry()
    definitions = get_series_definitions()
    target_series = registry["model"]["target_series"]
    alpha = float(registry["model"].get("ridge_alpha", 10.0))
    interval = float(registry["model"].get("prediction_interval", 0.80))

    observations = repository.latest_observations(
        [definition.series_id for definition in definitions]
    )
    dataset = build_bridge_dataset(observations, definitions, target_series)

    bridge = fit_bridge_ridge(
        dataset.training_frame,
        dataset.current_features,
        alpha=alpha,
        interval=interval,
    )
    ar1 = fit_ar1(dataset.training_frame["target"], interval=interval)
    ensemble = combine_equal_weight(bridge, ar1, interval=interval)

    run_id = str(uuid.uuid4())
    created_at = datetime.utcnow()

    metrics = {
        "training_observations": int(len(dataset.training_frame)),
        "feature_count": int(len(dataset.feature_names)),
        "imputed_features": dataset.imputed_features,
        "bridge_rmse": bridge.sigma,
        "ar1_rmse": ar1.sigma,
        "ensemble_sigma": ensemble.sigma,
        "interval": interval,
    }

    run_record = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_name": ensemble.model_name,
                "target_series": target_series,
                "run_timestamp": created_at,
                "data_as_of": dataset.data_as_of.date(),
                "target_period": str(dataset.target_period),
                "status": "success",
                "metrics_json": json.dumps(metrics),
                "notes": (
                    "Phase 1 bridge/AR ensemble. Missing current-quarter features "
                    "use a transparent no-news carry-forward assumption."
                ),
            }
        ]
    )

    forecast_rows = []
    coefficient_rows = []
    for result in [bridge, ar1, ensemble]:
        forecast_rows.append(
            {
                "run_id": run_id,
                "model_name": result.model_name,
                "target_series": target_series,
                "target_period": str(dataset.target_period),
                "point_forecast": result.point_forecast,
                "lower_80": result.lower,
                "upper_80": result.upper,
                "created_at": created_at,
            }
        )
        for feature, coefficient in result.coefficients.items():
            coefficient_rows.append(
                {
                    "run_id": run_id,
                    "model_name": result.model_name,
                    "feature": str(feature),
                    "coefficient": float(coefficient),
                }
            )

    forecasts = pd.DataFrame(forecast_rows)
    coefficients = pd.DataFrame(coefficient_rows)
    repository.save_model_outputs(run_record, forecasts, coefficients)

    return {
        "run_id": run_id,
        "target_period": str(dataset.target_period),
        "data_as_of": dataset.data_as_of.date().isoformat(),
        "forecasts": forecasts,
        "coefficients": coefficients,
        "metrics": metrics,
    }

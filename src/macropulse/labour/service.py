from __future__ import annotations

import json
import uuid
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.config import get_labour_model_config, target_definitions
from macropulse.labour.dataset import build_target_dataset
from macropulse.labour.models import fit_model_suite
from macropulse.labour.versioning import current_labour_model_identity


def run_labour_nowcast_suite(
    repository: MacroRepository | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    observations = repository.latest_observations()
    if observations.empty:
        raise RuntimeError("No FRED observations are stored. Run download_labour_data.py first.")

    config = get_labour_model_config()
    identity = current_labour_model_identity()
    run_id = str(uuid.uuid4())
    timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    data_as_of = pd.to_datetime(observations["observation_date"]).max().date()
    forecast_rows: list[dict] = []
    coefficient_rows: list[dict] = []
    target_metrics: dict[str, dict] = {}

    for definition in target_definitions():
        dataset = build_target_dataset(observations, definition.series_id)
        models = fit_model_suite(dataset.X, dataset.y, dataset.forecast_X, config)
        for result in models:
            forecast_rows.append(
                {
                    "run_id": run_id,
                    "target_series": definition.series_id,
                    "target_name": definition.name,
                    "target_unit": definition.unit,
                    "display_decimals": definition.display_decimals,
                    "target_period": str(dataset.target_period),
                    "model_name": result.model_name,
                    "point_forecast": result.point_forecast,
                    "lower_80": result.lower_80,
                    "upper_80": result.upper_80,
                    "diagnostics_json": json.dumps(result.diagnostics, default=str),
                    "created_at": timestamp,
                }
            )
            for feature, coefficient in result.coefficients.items():
                coefficient_rows.append(
                    {
                        "run_id": run_id,
                        "target_series": definition.series_id,
                        "model_name": result.model_name,
                        "feature": feature,
                        "coefficient": coefficient,
                    }
                )
        target_metrics[definition.series_id] = {
            "target_name": definition.name,
            "target_unit": definition.unit,
            "display_decimals": definition.display_decimals,
            "target_transform": definition.transform,
            "target_period": str(dataset.target_period),
            "latest_observed_period": str(dataset.latest_observed_period),
            "latest_level": dataset.latest_level,
            "latest_target_value": dataset.latest_target_value,
            "recent_three_month_mean": dataset.recent_three_month_mean,
            "twelve_month_level_change": dataset.twelve_month_level_change,
            "latest_yoy_growth": dataset.latest_yoy_growth,
            "training_observations": len(dataset.y),
            "feature_count": len(dataset.X.columns),
            "feature_ages": dataset.feature_ages,
            "imputed_features": dataset.imputed_features,
        }

    run_record = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "run_timestamp": timestamp,
                "status": "success",
                "data_as_of": data_as_of,
                "metrics_json": json.dumps({"targets": target_metrics}, default=str),
                "notes": (
                    "Model 1C development foundation. Latest-revised information set; "
                    "not vintage validated or production approved."
                ),
            }
        ]
    )
    forecasts = pd.DataFrame(forecast_rows)
    coefficients = pd.DataFrame(
        coefficient_rows,
        columns=["run_id", "target_series", "model_name", "feature", "coefficient"],
    )
    repository.save_labour_outputs(run_record, forecasts, coefficients)
    return {
        "run_id": run_id,
        "identity": identity.as_dict(),
        "data_as_of": data_as_of,
        "forecasts": forecasts,
        "metrics": target_metrics,
    }

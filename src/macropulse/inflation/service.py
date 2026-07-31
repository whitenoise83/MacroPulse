from __future__ import annotations

import json
import uuid

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import get_inflation_model_config, target_definitions
from macropulse.inflation.dataset import build_target_dataset
from macropulse.inflation.models import (
    combine_equal_weight,
    fit_ar1,
    fit_ridge_bridge,
    fit_rolling_mean,
)
from macropulse.inflation.versioning import current_inflation_model_identity


def run_inflation_nowcast_suite(repository: MacroRepository | None = None) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    definitions = target_definitions()
    all_series = repository.latest_observations()
    if all_series.empty:
        raise RuntimeError("No FRED observations are stored. Run download_inflation_data.py first.")
    config = get_inflation_model_config()
    identity = current_inflation_model_identity()
    run_id = str(uuid.uuid4())
    timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    forecast_rows: list[dict] = []
    coefficient_rows: list[dict] = []
    target_metrics: dict[str, dict] = {}

    for definition in definitions:
        dataset = build_target_dataset(all_series, definition.series_id)
        minimum = int(config.get("minimum_training_observations", 120))
        if len(dataset.y) < minimum:
            raise ValueError(
                f"{definition.series_id} has {len(dataset.y)} complete observations; "
                f"at least {minimum} are required."
            )
        coverage = float(config.get("interval_coverage", 0.80))
        ridge = fit_ridge_bridge(
            dataset.X,
            dataset.y,
            dataset.forecast_X,
            alpha=float(config.get("ridge_alpha", 8.0)),
            coverage=coverage,
        )
        ar1 = fit_ar1(dataset.y, coverage=coverage)
        mean = fit_rolling_mean(
            dataset.y,
            window=int(config.get("rolling_mean_window", 12)),
            coverage=coverage,
        )
        ensemble = combine_equal_weight(ridge, ar1, dataset.y, coverage=coverage)
        models = [ridge, ar1, mean, ensemble]
        for result in models:
            forecast_rows.append({
                "run_id": run_id,
                "target_series": definition.series_id,
                "target_name": definition.name,
                "target_period": str(dataset.target_period),
                "model_name": result.model_name,
                "point_forecast": result.point_forecast,
                "lower_80": result.lower_80,
                "upper_80": result.upper_80,
                "created_at": timestamp,
            })
            for feature, coefficient in result.coefficients.items():
                coefficient_rows.append({
                    "run_id": run_id,
                    "target_series": definition.series_id,
                    "model_name": result.model_name,
                    "feature": feature,
                    "coefficient": coefficient,
                })
        target_metrics[definition.series_id] = {
            "target_name": definition.name,
            "target_period": str(dataset.target_period),
            "latest_observed_period": str(dataset.latest_observed_period),
            "latest_index_value": dataset.latest_index_value,
            "latest_monthly_annualised": dataset.latest_mom_annualised,
            "latest_three_month_annualised": dataset.latest_three_month_annualised,
            "latest_year_over_year": dataset.latest_yoy,
            "training_observations": len(dataset.y),
            "feature_count": dataset.X.shape[1],
            "feature_ages": dataset.feature_ages,
            "imputed_features": dataset.imputed_features,
            "models": {result.model_name: result.diagnostics for result in models},
        }

    run_record = pd.DataFrame([{
        "run_id": run_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "run_timestamp": timestamp,
        "status": "success",
        "data_as_of": pd.to_datetime(all_series["observation_date"]).max().date(),
        "metrics_json": json.dumps({
            "model_identity": identity.as_dict(),
            "research_status": "development_vintage_backtest_available",
            "preferred_model": str(config.get("preferred_model", "Inflation Bridge Ridge")),
            "targets": target_metrics,
        }, default=str),
        "notes": "Model 1B v0.2 baseline research nowcast. Vintage validation is available, but the model is not approved for production use.",
    }])
    forecasts = pd.DataFrame(forecast_rows)
    coefficients = pd.DataFrame(coefficient_rows, columns=[
        "run_id", "target_series", "model_name", "feature", "coefficient"
    ])
    repository.save_inflation_outputs(run_record, forecasts, coefficients)
    return {
        "run_id": run_id,
        "identity": identity.as_dict(),
        "data_as_of": run_record.iloc[0]["data_as_of"],
        "forecasts": forecasts,
        "metrics": target_metrics,
    }

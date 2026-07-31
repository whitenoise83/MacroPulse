from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.config import get_inflation_model_config, target_definitions
from macropulse.inflation.dataset import build_target_dataset
from macropulse.inflation.live import run_governed_inflation_nowcast
from macropulse.inflation.models import (
    combine_equal_weight,
    fit_ar1,
    fit_ridge_bridge,
    fit_rolling_mean,
)
from macropulse.inflation.versioning import current_inflation_model_identity


def _run_legacy_suite(repository: Any) -> dict[str, Any]:
    """Compatibility path for lightweight repositories used by old unit tests."""
    definitions = target_definitions()
    all_series = repository.latest_observations()
    if all_series.empty:
        raise RuntimeError("No FRED observations are stored.")
    config = get_inflation_model_config()
    identity = current_inflation_model_identity()
    run_id = str(uuid.uuid4())
    timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    forecast_rows: list[dict] = []
    coefficient_rows: list[dict] = []
    target_metrics: dict[str, dict] = {}
    for definition in definitions:
        dataset = build_target_dataset(all_series, definition.series_id)
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
            forecast_rows.append(
                {
                    "run_id": run_id,
                    "target_series": definition.series_id,
                    "target_name": definition.name,
                    "target_period": str(dataset.target_period),
                    "model_name": result.model_name,
                    "point_forecast": result.point_forecast,
                    "lower_80": result.lower_80,
                    "upper_80": result.upper_80,
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
            "target_period": str(dataset.target_period),
            "latest_observed_period": str(dataset.latest_observed_period),
            "latest_monthly_annualised": dataset.latest_mom_annualised,
            "latest_three_month_annualised": dataset.latest_three_month_annualised,
            "latest_year_over_year": dataset.latest_yoy,
        }
    run_record = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "run_timestamp": timestamp,
                "status": "success",
                "data_as_of": pd.to_datetime(all_series["observation_date"]).max().date(),
                "metrics_json": json.dumps({"targets": target_metrics}, default=str),
                "notes": "Legacy compatibility suite; governed registration unavailable.",
            }
        ]
    )
    forecasts = pd.DataFrame(forecast_rows)
    coefficients = pd.DataFrame(
        coefficient_rows,
        columns=["run_id", "target_series", "model_name", "feature", "coefficient"],
    )
    repository.save_inflation_outputs(run_record, forecasts, coefficients)
    return {
        "run_id": run_id,
        "identity": identity.as_dict(),
        "data_as_of": run_record.iloc[0]["data_as_of"],
        "forecasts": forecasts,
        "metrics": target_metrics,
    }


def run_inflation_nowcast_suite(
    repository: MacroRepository | None = None,
    information_cutoff: date | None = None,
    build_news: bool = True,
) -> dict[str, Any]:
    """Run the governed Model 1B live candidate suite.

    The historical function name is retained for CLI and Streamlit compatibility.
    A minimal legacy path is used only by old lightweight test repositories that do
    not implement the governed registry methods.
    """
    repository = repository or MacroRepository()
    if not hasattr(repository, "register_model_identity"):
        repository.initialise()
        return _run_legacy_suite(repository)
    return run_governed_inflation_nowcast(
        repository=repository,
        information_cutoff=information_cutoff,
        build_news=build_news,
    )

from __future__ import annotations

import json
import uuid
from datetime import date

import numpy as np
import pandas as pd

from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import information_set_hash
from macropulse.inflation.config import (
    get_inflation_model_config,
    get_inflation_series_definitions,
    target_definitions,
)
from macropulse.inflation.dataset import build_target_dataset
from macropulse.inflation.models import (
    combine_equal_weight,
    fit_ar1,
    fit_ridge_bridge,
    fit_rolling_mean,
)
from macropulse.inflation.stages import (
    INFLATION_FORECAST_STAGES,
    inflation_stage_forecast_date,
    validate_inflation_stage_codes,
)
from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.inflation.vintage import (
    ensure_inflation_snapshot,
    is_recent_unreleased_month,
    target_actual_from_release_snapshot,
)


def _metric_block(frame: pd.DataFrame) -> dict[str, float | int]:
    if frame.empty:
        return {}
    errors = pd.to_numeric(frame["error"], errors="coerce").dropna().astype(float)
    return {
        "observations": int(len(errors)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(np.mean(np.abs(errors))),
        "bias": float(np.mean(errors)),
        "median_ae": float(np.median(np.abs(errors))),
        "max_abs_error": float(np.max(np.abs(errors))),
        "interval_coverage": float(frame["interval_covered"].mean()),
        "average_days_to_release": float(frame["days_to_release"].mean()),
    }


def _metrics(results: pd.DataFrame) -> dict:
    nested: dict[str, dict] = {}
    if results.empty:
        return nested
    for (target, stage, model), frame in results.groupby(
        ["target_series", "forecast_stage", "model_name"]
    ):
        nested.setdefault(str(target), {}).setdefault(str(stage), {})[str(model)] = (
            _metric_block(frame)
        )
    return nested


def _target_period_present(
    snapshot: pd.DataFrame,
    target_series: str,
    target_period: pd.Period,
) -> bool:
    rows = snapshot.loc[snapshot["series_id"] == target_series]
    if rows.empty:
        return False
    periods = pd.to_datetime(rows["observation_date"]).dt.to_period("M")
    return bool((periods == target_period).any())


def run_vintage_inflation_backtest(
    repository: MacroRepository | None = None,
    client: FredClient | None = None,
    start_period: str = "2015-01",
    end_period: str | None = None,
    target_ids: list[str] | None = None,
    stage_codes: list[str] | tuple[str, ...] | None = None,
    refresh_snapshots: bool = False,
    pause_seconds: float = 0.10,
) -> dict:
    """Run a release-staged pseudo-real-time ALFRED inflation backtest."""
    repository = repository or MacroRepository()
    repository.initialise()
    client = client or FredClient()
    identity = current_inflation_model_identity()
    config = get_inflation_model_config()
    all_definitions = get_inflation_series_definitions()
    definition_by_id = {item.series_id: item for item in all_definitions}
    target_map = {item.series_id: item for item in target_definitions()}

    selected_targets = target_ids or list(target_map)
    unknown_targets = [item for item in selected_targets if item not in target_map]
    if unknown_targets:
        raise ValueError(f"Unknown inflation targets: {unknown_targets}")
    selected_stages = validate_inflation_stage_codes(
        list(stage_codes) if stage_codes else [item.code for item in INFLATION_FORECAST_STAGES]
    )

    start = pd.Period(start_period, freq="M")
    end = pd.Period(end_period, freq="M") if end_period else pd.Timestamp(date.today()).to_period("M")
    periods = pd.period_range(start, end, freq="M")
    backtest_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    coverage = float(config.get("interval_coverage", 0.80))
    minimum = int(config.get("minimum_training_observations", 120))
    rows: list[dict] = []
    notices: list[dict] = []

    series_ids = list(definition_by_id)
    for target_id in selected_targets:
        target_definition = target_map[target_id]
        for number, target_period in enumerate(periods, start=1):
            release_date = repository.initial_release_date(target_id, target_period)
            if release_date is None:
                kind = "pending" if is_recent_unreleased_month(target_period) else "missing_release"
                notices.append(
                    {
                        "target_series": target_id,
                        "target_period": str(target_period),
                        "kind": kind,
                        "message": (
                            f"No initial-release date is stored for {target_id} {target_period}."
                        ),
                    }
                )
                continue

            try:
                ensure_inflation_snapshot(
                    repository,
                    client,
                    target_definition,
                    release_date,
                    refresh=refresh_snapshots,
                    pause_seconds=pause_seconds,
                )
                release_snapshot = repository.historical_snapshot(
                    release_date, [target_id]
                )
                actual = target_actual_from_release_snapshot(
                    release_snapshot, target_definition, target_period
                )
            except Exception as exc:
                # A prolonged upstream API failure for one release must not abort
                # a multi-hour backtest. The issue is stored and can be filled by
                # rerunning later; successfully cached snapshots remain reusable.
                notices.append(
                    {
                        "target_series": target_id,
                        "target_period": str(target_period),
                        "kind": "release_snapshot_error",
                        "message": str(exc),
                    }
                )
                print(
                    f"  Release snapshot unavailable for {target_id} {target_period}; "
                    "recording the issue and continuing.",
                    flush=True,
                )
                continue

            for stage_code in selected_stages:
                forecast_date = inflation_stage_forecast_date(
                    target_period, stage_code, release_date
                )
                if forecast_date >= release_date:
                    notices.append(
                        {
                            "target_series": target_id,
                            "target_period": str(target_period),
                            "forecast_stage": stage_code,
                            "kind": "invalid_cutoff",
                            "message": (
                                f"Forecast cutoff {forecast_date} is not before release "
                                f"date {release_date}."
                            ),
                        }
                    )
                    continue

                print(
                    f"[{target_id} | {number}/{len(periods)} | {stage_code}] "
                    f"{target_period} as of {forecast_date}",
                    flush=True,
                )
                try:
                    for definition in all_definitions:
                        ensure_inflation_snapshot(
                            repository,
                            client,
                            definition,
                            forecast_date,
                            refresh=refresh_snapshots,
                            pause_seconds=pause_seconds,
                        )
                    snapshot = repository.historical_snapshot(forecast_date, series_ids)
                    if snapshot.empty:
                        raise ValueError("Historical information set is empty.")
                    target_leakage = _target_period_present(
                        snapshot, target_id, target_period
                    )
                    if target_leakage:
                        raise ValueError(
                            f"Target-period value {target_id} {target_period} is present "
                            "before its declared initial release."
                        )
                    future_rows = pd.to_datetime(snapshot["observation_date"]).dt.date > forecast_date
                    if bool(future_rows.any()):
                        raise ValueError("Information set contains future-dated observations.")

                    dataset = build_target_dataset(
                        snapshot, target_id, target_period=target_period
                    )
                    if len(dataset.y) < minimum:
                        raise ValueError(
                            f"Only {len(dataset.y)} complete training months are available; "
                            f"{minimum} are required."
                        )
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
                    ensemble = combine_equal_weight(
                        ridge, ar1, dataset.y, coverage=coverage
                    )
                    info_hash = information_set_hash(snapshot)
                    for result in [ridge, ar1, mean, ensemble]:
                        error = float(actual - result.point_forecast)
                        rows.append(
                            {
                                "backtest_id": backtest_id,
                                "target_series": target_id,
                                "forecast_stage": stage_code,
                                "forecast_date": forecast_date,
                                "target_period": str(target_period),
                                "actual_release_date": release_date,
                                "days_to_release": int((release_date - forecast_date).days),
                                "model_name": result.model_name,
                                "point_forecast": result.point_forecast,
                                "actual": actual,
                                "error": error,
                                "abs_error": abs(error),
                                "squared_error": error**2,
                                "lower_80": result.lower_80,
                                "upper_80": result.upper_80,
                                "interval_covered": bool(
                                    result.lower_80 <= actual <= result.upper_80
                                ),
                                "imputed_feature_count": len(dataset.imputed_features),
                                "information_set_hash": info_hash,
                                "max_observation_date": pd.to_datetime(
                                    snapshot["observation_date"]
                                ).max().date(),
                                "training_observations": len(dataset.y),
                                "target_leakage": False,
                                "created_at": created_at,
                            }
                        )
                except Exception as exc:
                    message = str(exc)
                    kind = (
                        "warmup"
                        if "complete training months are available" in message
                        else "stage_error"
                    )
                    notices.append(
                        {
                            "target_series": target_id,
                            "target_period": str(target_period),
                            "forecast_stage": stage_code,
                            "forecast_date": str(forecast_date),
                            "kind": kind,
                            "message": message,
                        }
                    )

    results = pd.DataFrame(rows)
    metric_payload = _metrics(results)
    errors = [
        notice
        for notice in notices
        if notice.get("kind") not in {"pending", "warmup"}
    ]
    status = "success" if not errors else "partial"
    run_record = pd.DataFrame(
        [
            {
                "backtest_id": backtest_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "created_at": created_at,
                "start_period": str(start),
                "end_period": str(end),
                "target_series_json": json.dumps(selected_targets),
                "stages_json": json.dumps(selected_stages),
                "status": status,
                "config_json": json.dumps(config, default=str),
                "metrics_json": json.dumps(metric_payload, default=str),
                "notices_json": json.dumps(notices, default=str),
                "notes": (
                    "Pseudo-real-time ALFRED backtest. Forecast information sets use "
                    "historical realtime cutoffs; outcomes use the target's initial-release snapshot."
                ),
            }
        ]
    )
    expected_columns = [
        "backtest_id",
        "target_series",
        "forecast_stage",
        "forecast_date",
        "target_period",
        "actual_release_date",
        "days_to_release",
        "model_name",
        "point_forecast",
        "actual",
        "error",
        "abs_error",
        "squared_error",
        "lower_80",
        "upper_80",
        "interval_covered",
        "imputed_feature_count",
        "information_set_hash",
        "max_observation_date",
        "training_observations",
        "target_leakage",
        "created_at",
    ]
    if results.empty:
        results = pd.DataFrame(columns=expected_columns)
    else:
        results = results[expected_columns]
    repository.save_inflation_vintage_backtest_outputs(run_record, results)
    return {
        "backtest_id": backtest_id,
        "status": status,
        "results": results,
        "metrics": metric_payload,
        "notices": notices,
    }

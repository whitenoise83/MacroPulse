from __future__ import annotations

import json
import uuid
from datetime import date

import numpy as np
import pandas as pd

from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import information_set_hash
from macropulse.labour.config import (
    get_labour_model_config,
    get_labour_series_definitions,
    target_definitions,
)
from macropulse.labour.dataset import build_target_dataset
from macropulse.labour.models import fit_model_suite
from macropulse.labour.stages import (
    LABOUR_FORECAST_STAGES,
    labour_stage_forecast_date,
    validate_labour_stage_codes,
)
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.labour.vintage import (
    ensure_labour_snapshot,
    is_recent_unreleased_month,
    structural_missing_reason,
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
        "p90_abs_error": float(np.quantile(np.abs(errors), 0.90)),
        "max_abs_error": float(np.max(np.abs(errors))),
        "directional_accuracy": float(frame["direction_correct"].mean()),
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
        nested.setdefault(str(target), {}).setdefault(str(stage), {})[str(model)] = _metric_block(frame)
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


def _direction_correct(
    transform: str,
    point_forecast: float,
    actual: float,
    previous_actual: float,
) -> bool:
    if transform == "level":
        return bool(np.sign(point_forecast - previous_actual) == np.sign(actual - previous_actual))
    return bool(np.sign(point_forecast) == np.sign(actual))


def _regime(target_period: pd.Period) -> str:
    if target_period < pd.Period("2020-03", freq="M"):
        return "pre_pandemic"
    if target_period <= pd.Period("2021-12", freq="M"):
        return "pandemic_dislocation"
    return "post_2021"


def run_vintage_labour_backtest(
    repository: MacroRepository | None = None,
    client: FredClient | None = None,
    start_period: str = "2016-01",
    end_period: str | None = None,
    target_ids: list[str] | None = None,
    stage_codes: list[str] | tuple[str, ...] | None = None,
    refresh_snapshots: bool = False,
    pause_seconds: float = 0.15,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    client = client or FredClient()
    identity = current_labour_model_identity()
    config = get_labour_model_config()
    all_definitions = get_labour_series_definitions()
    target_map = {item.series_id: item for item in target_definitions()}

    selected_targets = target_ids or list(target_map)
    unknown_targets = [item for item in selected_targets if item not in target_map]
    if unknown_targets:
        raise ValueError(f"Unknown labour targets: {unknown_targets}")
    selected_stages = validate_labour_stage_codes(
        list(stage_codes) if stage_codes else [item.code for item in LABOUR_FORECAST_STAGES]
    )

    start = pd.Period(start_period, freq="M")
    end = pd.Period(end_period, freq="M") if end_period else pd.Timestamp(date.today()).to_period("M")
    periods = pd.period_range(start, end, freq="M")
    backtest_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    minimum = int(config.get("minimum_training_observations", 120))
    rows: list[dict] = []
    notices: list[dict] = []
    series_ids = [item.series_id for item in all_definitions]

    for target_id in selected_targets:
        target_definition = target_map[target_id]
        for number, target_period in enumerate(periods, start=1):
            release_date = repository.initial_release_date(target_id, target_period)
            if release_date is None:
                structural_reason = structural_missing_reason(target_id, target_period)
                if structural_reason is not None:
                    kind = "structural_missing"
                    message = structural_reason
                elif is_recent_unreleased_month(target_period):
                    kind = "pending"
                    message = f"No initial-release date is stored yet for {target_id} {target_period}."
                else:
                    kind = "missing_release"
                    message = f"No initial-release date is stored for {target_id} {target_period}."
                notices.append({
                    "target_series": target_id,
                    "target_period": str(target_period),
                    "kind": kind,
                    "message": message,
                })
                continue

            try:
                ensure_labour_snapshot(
                    repository, client, target_definition, release_date,
                    refresh=refresh_snapshots, pause_seconds=pause_seconds,
                )
                release_snapshot = repository.historical_snapshot(release_date, [target_id])
                actual = target_actual_from_release_snapshot(
                    release_snapshot, target_definition, target_period
                )
            except Exception as exc:
                notices.append({
                    "target_series": target_id,
                    "target_period": str(target_period),
                    "kind": "release_snapshot_error",
                    "message": str(exc),
                })
                print(
                    f"  Release snapshot unavailable for {target_id} {target_period}; "
                    "recording the issue and continuing.",
                    flush=True,
                )
                continue

            for stage_code in selected_stages:
                forecast_date = labour_stage_forecast_date(target_period, stage_code, release_date)
                if forecast_date >= release_date:
                    notices.append({
                        "target_series": target_id,
                        "target_period": str(target_period),
                        "forecast_stage": stage_code,
                        "kind": "invalid_cutoff",
                        "message": f"Forecast cutoff {forecast_date} is not before release date {release_date}.",
                    })
                    continue

                print(
                    f"[{target_id} | {number}/{len(periods)} | {stage_code}] "
                    f"{target_period} as of {forecast_date}",
                    flush=True,
                )
                try:
                    for definition in all_definitions:
                        ensure_labour_snapshot(
                            repository, client, definition, forecast_date,
                            refresh=refresh_snapshots, pause_seconds=pause_seconds,
                        )
                    snapshot = repository.historical_snapshot(forecast_date, series_ids)
                    if snapshot.empty:
                        raise ValueError("Historical information set is empty.")
                    target_leakage = _target_period_present(snapshot, target_id, target_period)
                    if target_leakage:
                        raise ValueError(
                            f"Target-period value {target_id} {target_period} is present before its initial release."
                        )
                    dates = pd.to_datetime(snapshot["observation_date"]).dt.date
                    if bool((dates > forecast_date).any()):
                        raise ValueError("Information set contains future-dated observations.")

                    dataset = build_target_dataset(snapshot, target_id, target_period=target_period)
                    if len(dataset.y) < minimum:
                        notices.append({
                            "target_series": target_id,
                            "target_period": str(target_period),
                            "forecast_stage": stage_code,
                            "kind": "training_warmup",
                            "message": f"Only {len(dataset.y)} complete training months are available; {minimum} are required.",
                        })
                        continue
                    models = fit_model_suite(dataset.X, dataset.y, dataset.forecast_X, config)
                    info_hash = information_set_hash(snapshot)
                    previous_actual = float(dataset.y.iloc[-1])
                    for result in models:
                        error = float(actual - result.point_forecast)
                        rows.append({
                            "backtest_id": backtest_id,
                            "target_series": target_id,
                            "target_name": target_definition.name,
                            "target_unit": target_definition.unit,
                            "forecast_stage": stage_code,
                            "forecast_date": forecast_date,
                            "target_period": str(target_period),
                            "actual_release_date": release_date,
                            "days_to_release": int((release_date - forecast_date).days),
                            "model_name": result.model_name,
                            "point_forecast": float(result.point_forecast),
                            "actual": float(actual),
                            "error": error,
                            "abs_error": abs(error),
                            "squared_error": error**2,
                            "direction_correct": _direction_correct(
                                target_definition.transform,
                                float(result.point_forecast), float(actual), previous_actual,
                            ),
                            "lower_80": float(result.lower_80),
                            "upper_80": float(result.upper_80),
                            "interval_covered": bool(result.lower_80 <= actual <= result.upper_80),
                            "training_observations": int(len(dataset.y)),
                            "imputed_feature_count": int(len(dataset.imputed_features)),
                            "information_set_hash": info_hash,
                            "target_leakage": bool(target_leakage),
                            "max_observation_date": max(dates),
                            "regime": _regime(target_period),
                            "created_at": created_at,
                        })
                except Exception as exc:
                    notices.append({
                        "target_series": target_id,
                        "target_period": str(target_period),
                        "forecast_stage": stage_code,
                        "kind": "forecast_error",
                        "message": str(exc),
                    })
                    print(f"  Stage unavailable: {exc}", flush=True)
                    continue

    results = pd.DataFrame(rows)
    metrics = _metrics(results)
    hard_issues = [
        item
        for item in notices
        if item.get("kind") not in {"pending", "training_warmup", "structural_missing"}
    ]
    status = "success" if not hard_issues else "partial"
    run_record = pd.DataFrame([{
        "backtest_id": backtest_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "created_at": created_at,
        "start_period": str(start),
        "end_period": str(end),
        "status": status,
        "stage_codes_json": json.dumps(list(selected_stages)),
        "target_series_json": json.dumps(selected_targets),
        "metrics_json": json.dumps(metrics, default=str),
        "notices_json": json.dumps(notices, default=str),
        "notes": (
            "Release-staged pseudo-real-time ALFRED labour backtest. Initial-release "
            "outcomes and historical information sets; raw intervals remain developmental."
        ),
    }])
    repository.save_labour_vintage_backtest_outputs(run_record, results)
    return {
        "backtest_id": backtest_id,
        "status": status,
        "results": results,
        "metrics": metrics,
        "notices": notices,
        "hard_issues": hard_issues,
    }

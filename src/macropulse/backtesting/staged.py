from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Callable

import numpy as np
import pandas as pd

from macropulse.backtesting.intervals import calibrate_forecast_interval
from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    calculate_stage_metrics,
    estimate_inverse_rmse_weights,
)
from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
    build_stable_stage_policy,
    select_robust_stage_candidate,
)
from macropulse.backtesting.stages import stage_forecast_date, validate_stage_codes
from macropulse.backtesting.vintage import (
    ensure_snapshot,
    is_recent_unreleased_period,
    target_actual_from_snapshot,
)
from macropulse.config import get_series_definitions, load_registry
from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import current_model_identity, information_set_hash
from macropulse.models.baseline import ForecastResult, combine_weighted, fit_ar1, fit_bridge_ridge
from macropulse.models.dynamic_factor import fit_dynamic_factor
from macropulse.processing.dataset import build_bridge_dataset
from macropulse.processing.mixed_frequency import build_mixed_frequency_dataset


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class StageBacktestConfig:
    start_date: str = "2020-01-01"
    end_date: str = date.today().isoformat()
    stages: tuple[str, ...] = (
        "early_quarter",
        "after_month_1",
        "after_month_2",
        "quarter_end",
        "pre_advance_release",
    )
    refresh_snapshots: bool = False
    request_pause_seconds: float = 0.10
    include_dfm: bool = True
    rolling_window: int = 12
    rolling_min_history: int = 8
    rolling_min_weight: float = 0.10
    rolling_max_weight: float = 0.70
    interval_window: int = 20
    interval_min_history: int = 12
    interval_coverage: float = 0.80
    selection_window: int = 20
    selection_min_history: int = 20
    selection_fallback_model: str = "Bridge–DFM Ensemble"
    selection_switch_threshold: float = 0.05
    selection_tail_ratio_limit: float = 1.10
    selection_maximum_error_ratio_limit: float = 1.25

    def __post_init__(self) -> None:
        validate_stage_codes(self.stages)


def _target_periods(start_date: str, end_date: str) -> list[pd.Period]:
    start = pd.Timestamp(start_date)
    end = min(pd.Timestamp(end_date), pd.Timestamp(date.today()))
    if start > end:
        raise ValueError("Stage backtest start_date must not be after end_date.")
    return list(pd.period_range(start=start, end=end, freq="Q"))


def _metrics_to_dict(metrics: pd.DataFrame) -> dict:
    if metrics.empty:
        return {}
    output: dict[str, dict] = {}
    for row in metrics.to_dict(orient="records"):
        key = f"{row.pop('forecast_stage')}::{row.pop('model_name')}"
        output[key] = {
            name: (int(value) if name == "observations" else float(value))
            for name, value in row.items()
            if value is not None and not (isinstance(value, float) and np.isnan(value))
        }
    return output


def _prior_stage_results(rows: list[dict], stage_code: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    return frame.loc[frame["forecast_stage"] == stage_code].copy()


def _result_row(
    result: ForecastResult,
    raw_result: ForecastResult,
    interval_diagnostics: dict,
    stage_backtest_id: str,
    forecast_stage: str,
    forecast_date: date,
    target_period: pd.Period,
    release_date: date,
    actual: float,
    imputed_feature_count: int,
    information_hash: str,
    model_version: str,
    created_at: datetime,
) -> dict:
    error = float(result.point_forecast - actual)
    return {
        "stage_backtest_id": stage_backtest_id,
        "forecast_stage": forecast_stage,
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
        "direction_correct": bool(np.sign(result.point_forecast) == np.sign(actual)),
        "raw_lower_80": float(raw_result.lower),
        "raw_upper_80": float(raw_result.upper),
        "lower_80": float(result.lower),
        "upper_80": float(result.upper),
        "interval_width": float(result.upper - result.lower),
        "interval_covered": bool(result.lower <= actual <= result.upper),
        "interval_method": str(interval_diagnostics.get("method")),
        "interval_history": int(interval_diagnostics.get("history_count", 0)),
        "interval_details_json": json.dumps(interval_diagnostics),
        "imputed_feature_count": int(imputed_feature_count),
        "information_set_hash": information_hash,
        "model_version": model_version,
        "created_at": created_at,
    }


def run_staged_pseudo_realtime_backtest(
    config: StageBacktestConfig | None = None,
    repository: MacroRepository | None = None,
    client: FredClient | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Evaluate GDP nowcasts at several points within each target quarter.

    Each forecast is built from a FRED/ALFRED snapshot fixed at the stage cutoff.
    Ensemble weights and interval calibration use only earlier completed target
    quarters from the same forecast stage.
    """
    config = config or StageBacktestConfig()
    repository = repository or MacroRepository()
    client = client or FredClient()
    repository.initialise()

    registry = load_registry()
    definitions = get_series_definitions()
    definition_map = {definition.series_id: definition for definition in definitions}
    target_series = registry["model"]["target_series"]
    target_definition = definition_map[target_series]
    alpha = float(registry["model"].get("ridge_alpha", 10.0))
    interval = float(registry["model"].get("prediction_interval", 0.80))
    dfm_config = registry.get("dynamic_factor", {})
    identity = current_model_identity()

    target_periods = _target_periods(config.start_date, config.end_date)
    # end_date selects target quarters. A pre-release cutoff can legitimately
    # fall in the following quarter, so only today limits executable cutoffs.
    end_limit = date.today()
    stage_backtest_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []
    diagnostics_rows: list[dict] = []
    pending_outcomes: list[dict] = []
    skipped: list[dict] = []
    model_failures: list[dict] = []
    robust_incumbents: dict[str, str] = {}

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    for period_position, target_period in enumerate(target_periods, start=1):
        release_date = repository.initial_release_date(target_series, target_period)
        if release_date is None:
            item = {
                "scope": "pending_outcome" if is_recent_unreleased_period(target_period) else "quarter",
                "target_period": str(target_period),
                "reason": f"No initial-release date is stored for {target_series} {target_period}.",
            }
            if item["scope"] == "pending_outcome":
                pending_outcomes.append(item)
                report(f"[{period_position}/{len(target_periods)}] {target_period}: pending outcome")
            else:
                skipped.append(item)
                report(f"[{period_position}/{len(target_periods)}] {target_period}: skipped")
            continue

        try:
            release_timestamp = pd.Timestamp(release_date)
            ensure_snapshot(
                repository=repository,
                client=client,
                definition=target_definition,
                as_of_date=release_timestamp,
                refresh=config.refresh_snapshots,
                pause_seconds=config.request_pause_seconds,
            )
            actual_snapshot = repository.historical_snapshot(release_date, [target_series])
            actual = target_actual_from_snapshot(actual_snapshot, target_definition, target_period)
        except Exception as exc:
            skipped.append(
                {
                    "scope": "actual",
                    "target_period": str(target_period),
                    "reason": str(exc),
                }
            )
            report(f"[{period_position}/{len(target_periods)}] {target_period}: actual unavailable: {exc}")
            continue

        for stage_position, stage_code in enumerate(config.stages, start=1):
            forecast_date = stage_forecast_date(target_period, stage_code, release_date)
            if forecast_date > end_limit:
                continue
            if forecast_date >= release_date:
                skipped.append(
                    {
                        "scope": "stage",
                        "target_period": str(target_period),
                        "forecast_stage": stage_code,
                        "forecast_date": forecast_date.isoformat(),
                        "reason": "Forecast cutoff is not before the initial outcome release.",
                    }
                )
                continue

            report(
                f"[{period_position}/{len(target_periods)} | {stage_position}/{len(config.stages)}] "
                f"{target_period} {stage_code} as of {forecast_date}"
            )
            try:
                cutoff = pd.Timestamp(forecast_date)
                for definition in definitions:
                    ensure_snapshot(
                        repository=repository,
                        client=client,
                        definition=definition,
                        as_of_date=cutoff,
                        refresh=config.refresh_snapshots,
                        pause_seconds=config.request_pause_seconds,
                    )
                observations = repository.historical_snapshot(
                    forecast_date,
                    [definition.series_id for definition in definitions],
                )
                if observations.empty:
                    raise ValueError("The historical stage snapshot is empty.")
                info_hash = information_set_hash(observations)

                bridge_dataset = build_bridge_dataset(
                    observations=observations,
                    definitions=definitions,
                    target_series=target_series,
                    target_period=target_period,
                    data_as_of=cutoff,
                )
                bridge = fit_bridge_ridge(
                    bridge_dataset.training_frame,
                    bridge_dataset.current_features,
                    alpha=alpha,
                    interval=interval,
                )
                ar1 = fit_ar1(bridge_dataset.training_frame["target"], interval=interval)
                raw_results: list[ForecastResult] = [bridge, ar1]
                prior_stage = _prior_stage_results(rows, stage_code)

                if config.include_dfm:
                    try:
                        mixed_dataset = build_mixed_frequency_dataset(
                            observations=observations,
                            definitions=definitions,
                            target_series=target_series,
                            target_period=target_period,
                            data_as_of=cutoff,
                        )
                        dfm = fit_dynamic_factor(
                            dataset=mixed_dataset,
                            interval=interval,
                            factors=int(dfm_config.get("factors", 1)),
                            factor_orders=int(dfm_config.get("factor_orders", 1)),
                            idiosyncratic_ar1=bool(dfm_config.get("idiosyncratic_ar1", True)),
                            maxiter=int(dfm_config.get("maxiter", 100)),
                            tolerance=float(dfm_config.get("tolerance", 1e-4)),
                            require_convergence=bool(dfm_config.get("require_convergence", False)),
                        )
                        fixed = combine_weighted(
                            [bridge, dfm],
                            {"Bridge Ridge": 0.5, "Dynamic Factor Model": 0.5},
                            model_name="Bridge–DFM Ensemble",
                            interval=interval,
                            diagnostics={"weight_method": "equal"},
                        )
                        rolling_weights, weight_diagnostics = estimate_inverse_rmse_weights(
                            prior_stage,
                            model_names=("Bridge Ridge", "Dynamic Factor Model"),
                            window=config.rolling_window,
                            min_history=config.rolling_min_history,
                            min_weight=config.rolling_min_weight,
                            max_weight=config.rolling_max_weight,
                        )
                        if not prior_stage.empty:
                            maximum_date = pd.to_datetime(prior_stage["forecast_date"]).max()
                            weight_diagnostics["max_prior_forecast_date"] = maximum_date.date().isoformat()
                        else:
                            weight_diagnostics["max_prior_forecast_date"] = None
                        rolling = combine_weighted(
                            [bridge, dfm],
                            rolling_weights,
                            model_name="Rolling Bridge–DFM Ensemble",
                            interval=interval,
                            diagnostics=weight_diagnostics,
                        )
                        raw_results.extend([dfm, fixed, rolling])
                        stable_policy, stable_diagnostics = build_stable_stage_policy(
                            raw_results, forecast_stage=stage_code
                        )
                        robust_policy, robust_diagnostics = select_robust_stage_candidate(
                            raw_results,
                            prior_results=prior_stage,
                            forecast_stage=stage_code,
                            incumbent_model=robust_incumbents.get(stage_code),
                            window=config.selection_window,
                            min_history=config.selection_min_history,
                            switch_threshold=config.selection_switch_threshold,
                            tail_ratio_limit=config.selection_tail_ratio_limit,
                            maximum_error_ratio_limit=config.selection_maximum_error_ratio_limit,
                            fallback_model=config.selection_fallback_model,
                        )
                        robust_incumbents[stage_code] = str(
                            robust_diagnostics["selected_component"]
                        )
                        raw_results.extend([stable_policy, robust_policy])
                        diagnostics_rows.extend(
                            [
                                {
                                    "stage_backtest_id": stage_backtest_id,
                                    "forecast_stage": stage_code,
                                    "forecast_date": forecast_date,
                                    "target_period": str(target_period),
                                    "model_name": dfm.model_name,
                                    "status": "success",
                                    "converged": bool(dfm.diagnostics.get("converged")),
                                    "iterations": int(dfm.diagnostics.get("iterations", 0)),
                                    "details_json": json.dumps(dfm.diagnostics),
                                    "created_at": created_at,
                                },
                                {
                                    "stage_backtest_id": stage_backtest_id,
                                    "forecast_stage": stage_code,
                                    "forecast_date": forecast_date,
                                    "target_period": str(target_period),
                                    "model_name": rolling.model_name,
                                    "status": "success",
                                    "converged": None,
                                    "iterations": None,
                                    "details_json": json.dumps(weight_diagnostics),
                                    "created_at": created_at,
                                },
                                {
                                    "stage_backtest_id": stage_backtest_id,
                                    "forecast_stage": stage_code,
                                    "forecast_date": forecast_date,
                                    "target_period": str(target_period),
                                    "model_name": STABLE_STAGE_POLICY_NAME,
                                    "status": "success",
                                    "converged": None,
                                    "iterations": None,
                                    "details_json": json.dumps(stable_diagnostics),
                                    "created_at": created_at,
                                },
                                {
                                    "stage_backtest_id": stage_backtest_id,
                                    "forecast_stage": stage_code,
                                    "forecast_date": forecast_date,
                                    "target_period": str(target_period),
                                    "model_name": ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
                                    "status": "success",
                                    "converged": None,
                                    "iterations": None,
                                    "details_json": json.dumps(robust_diagnostics),
                                    "created_at": created_at,
                                },
                            ]
                        )
                    except Exception as exc:
                        failure = {
                            "scope": "model",
                            "target_period": str(target_period),
                            "forecast_stage": stage_code,
                            "forecast_date": forecast_date.isoformat(),
                            "model_name": "Dynamic Factor Model",
                            "reason": str(exc),
                        }
                        model_failures.append(failure)
                        diagnostics_rows.append(
                            {
                                "stage_backtest_id": stage_backtest_id,
                                "forecast_stage": stage_code,
                                "forecast_date": forecast_date,
                                "target_period": str(target_period),
                                "model_name": "Dynamic Factor Model",
                                "status": "failed",
                                "converged": False,
                                "iterations": None,
                                "details_json": json.dumps({"error": str(exc)}),
                                "created_at": created_at,
                            }
                        )
                        report(f"  DFM failed; benchmark forecasts retained: {exc}")

                if not any(
                    result.model_name == STABLE_STAGE_POLICY_NAME
                    for result in raw_results
                ):
                    stable_policy, stable_diagnostics = build_stable_stage_policy(
                        raw_results,
                        forecast_stage=stage_code,
                        fallback_model="Bridge Ridge",
                    )
                    stable_diagnostics["fallback_reason"] = (
                        "dfm_unavailable" if config.include_dfm else "dfm_disabled"
                    )
                    robust_policy, robust_diagnostics = select_robust_stage_candidate(
                        raw_results,
                        prior_results=prior_stage,
                        forecast_stage=stage_code,
                        incumbent_model="Bridge Ridge",
                        window=config.selection_window,
                        min_history=config.selection_min_history,
                        switch_threshold=config.selection_switch_threshold,
                        tail_ratio_limit=config.selection_tail_ratio_limit,
                        maximum_error_ratio_limit=config.selection_maximum_error_ratio_limit,
                        fallback_model="Bridge Ridge",
                    )
                    robust_diagnostics["fallback_reason"] = stable_diagnostics["fallback_reason"]
                    robust_incumbents[stage_code] = str(robust_diagnostics["selected_component"])
                    raw_results.extend([stable_policy, robust_policy])
                    for model_name, details in [
                        (STABLE_STAGE_POLICY_NAME, stable_diagnostics),
                        (ROBUST_STAGE_ADAPTIVE_MODEL_NAME, robust_diagnostics),
                    ]:
                        diagnostics_rows.append(
                            {
                                "stage_backtest_id": stage_backtest_id,
                                "forecast_stage": stage_code,
                                "forecast_date": forecast_date,
                                "target_period": str(target_period),
                                "model_name": model_name,
                                "status": "success",
                                "converged": None,
                                "iterations": None,
                                "details_json": json.dumps(details),
                                "created_at": created_at,
                            }
                        )

                for raw_result in raw_results:
                    calibrated, interval_diagnostics = calibrate_forecast_interval(
                        result=raw_result,
                        prior_results=prior_stage,
                        forecast_stage=stage_code,
                        coverage=config.interval_coverage,
                        window=config.interval_window,
                        min_history=config.interval_min_history,
                    )
                    rows.append(
                        _result_row(
                            result=calibrated,
                            raw_result=raw_result,
                            interval_diagnostics=interval_diagnostics,
                            stage_backtest_id=stage_backtest_id,
                            forecast_stage=stage_code,
                            forecast_date=forecast_date,
                            target_period=target_period,
                            release_date=release_date,
                            actual=actual,
                            imputed_feature_count=(
                                0
                                if raw_result.model_name == "Dynamic Factor Model"
                                or (
                                    raw_result.model_name in {STABLE_STAGE_POLICY_NAME, ROBUST_STAGE_ADAPTIVE_MODEL_NAME}
                                    and raw_result.diagnostics.get("selected_component")
                                    == "Dynamic Factor Model"
                                )
                                else len(bridge_dataset.imputed_features)
                            ),
                            information_hash=info_hash,
                            model_version=identity.model_version,
                            created_at=created_at,
                        )
                    )
            except Exception as exc:
                skipped.append(
                    {
                        "scope": "stage",
                        "target_period": str(target_period),
                        "forecast_stage": stage_code,
                        "forecast_date": forecast_date.isoformat(),
                        "reason": str(exc),
                    }
                )
                report(f"  stage skipped: {exc}")

    results = pd.DataFrame(rows)
    diagnostics = pd.DataFrame(diagnostics_rows)
    stage_metrics = calculate_stage_metrics(results)
    full_metrics = calculate_backtest_metrics(results) if not results.empty else pd.DataFrame()
    issues = skipped + model_failures
    status = "success" if not issues and not results.empty else (
        "partial" if not results.empty else "failed"
    )
    run_record = pd.DataFrame(
        [
            {
                "stage_backtest_id": stage_backtest_id,
                "created_at": created_at,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "target_series": target_series,
                "start_date": pd.Timestamp(config.start_date).date(),
                "end_date": pd.Timestamp(config.end_date).date(),
                "status": status,
                "config_json": json.dumps(asdict(config)),
                "metrics_json": json.dumps(_metrics_to_dict(stage_metrics)),
                "notices_json": json.dumps(pending_outcomes + issues),
                "notes": (
                    "Pseudo-real-time GDP backtest at multiple within-quarter information cutoffs. "
                    "FRED vintages are fixed at each cutoff; rolling model weights and empirical "
                    "interval calibration and robust adaptive selection use only prior completed target quarters from the same stage; the stable stage policy is predeclared."
                ),
            }
        ]
    )
    repository.save_stage_backtest_outputs(run_record, results, diagnostics)
    return {
        "stage_backtest_id": stage_backtest_id,
        "status": status,
        "results": results,
        "metrics": full_metrics,
        "stage_metrics": stage_metrics,
        "diagnostics": diagnostics,
        "pending_outcomes": pending_outcomes,
        "skipped": skipped,
        "model_failures": model_failures,
    }

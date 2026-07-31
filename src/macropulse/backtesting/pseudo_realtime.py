from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Callable

import numpy as np
import pandas as pd

from macropulse.backtesting.vintage import (
    ensure_snapshot,
    is_recent_unreleased_period,
    target_actual_from_snapshot,
)
from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    calculate_regime_metrics,
    estimate_inverse_rmse_weights,
)
from macropulse.config import get_series_definitions, load_registry
from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.models.baseline import (
    ForecastResult,
    combine_equal_weight,
    combine_equal_weight_many,
    combine_weighted,
    fit_ar1,
    fit_bridge_ridge,
)
from macropulse.models.dynamic_factor import fit_dynamic_factor
from macropulse.processing.dataset import build_bridge_dataset
from macropulse.processing.mixed_frequency import build_mixed_frequency_dataset


ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class BacktestConfig:
    start_date: str = "2020-03-31"
    end_date: str = date.today().isoformat()
    refresh_snapshots: bool = False
    request_pause_seconds: float = 0.15
    include_dfm: bool = True
    include_legacy_ensembles: bool = False
    rolling_window: int = 12
    rolling_min_history: int = 8
    rolling_min_weight: float = 0.10
    rolling_max_weight: float = 0.70


def _quarter_end_dates(start_date: str, end_date: str) -> list[pd.Timestamp]:
    start = pd.Timestamp(start_date)
    end = min(pd.Timestamp(end_date), pd.Timestamp(date.today()))
    if start > end:
        raise ValueError("Backtest start_date must not be after end_date.")

    periods = pd.period_range(start=start, end=end, freq="Q")
    quarter_ends = [period.end_time.normalize() for period in periods]
    return [quarter_end for quarter_end in quarter_ends if quarter_end <= end]


def _metrics_to_dict(metrics: pd.DataFrame) -> dict:
    if metrics.empty:
        return {}
    output: dict[str, dict] = {}
    for row in metrics.to_dict(orient="records"):
        model_name = str(row.pop("model_name"))
        output[model_name] = {
            key: (int(value) if key == "observations" else float(value))
            for key, value in row.items()
        }
    return output


def _result_row(
    result: ForecastResult,
    backtest_id: str,
    forecast_date: pd.Timestamp,
    target_period: pd.Period,
    release_date: date,
    actual: float,
    imputed_feature_count: int,
    created_at: datetime,
) -> dict:
    error = float(result.point_forecast - actual)
    return {
        "backtest_id": backtest_id,
        "forecast_date": forecast_date.date(),
        "target_period": str(target_period),
        "actual_release_date": release_date,
        "model_name": result.model_name,
        "point_forecast": float(result.point_forecast),
        "actual": actual,
        "error": error,
        "abs_error": abs(error),
        "squared_error": error**2,
        "direction_correct": bool(np.sign(result.point_forecast) == np.sign(actual)),
        "lower_80": float(result.lower),
        "upper_80": float(result.upper),
        "interval_covered": bool(result.lower <= actual <= result.upper),
        "imputed_feature_count": int(imputed_feature_count),
        "created_at": created_at,
    }


def run_pseudo_realtime_backtest(
    config: BacktestConfig | None = None,
    repository: MacroRepository | None = None,
    client: FredClient | None = None,
    progress: ProgressCallback | None = None,
) -> dict:
    """Run a strictly vintage-aware quarter-end US GDP model comparison."""
    config = config or BacktestConfig()
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

    forecast_dates = _quarter_end_dates(config.start_date, config.end_date)
    backtest_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []
    diagnostics_rows: list[dict] = []
    skipped_quarters: list[dict] = []
    pending_outcomes: list[dict] = []
    model_failures: list[dict] = []

    def report(message: str) -> None:
        if progress is not None:
            progress(message)

    for position, forecast_date in enumerate(forecast_dates, start=1):
        target_period = forecast_date.to_period("Q")
        report(
            f"[{position}/{len(forecast_dates)}] Building vintage snapshot for "
            f"{forecast_date.date()} ({target_period})"
        )

        try:
            for definition in definitions:
                ensure_snapshot(
                    repository=repository,
                    client=client,
                    definition=definition,
                    as_of_date=forecast_date,
                    refresh=config.refresh_snapshots,
                    pause_seconds=config.request_pause_seconds,
                )

            observations = repository.historical_snapshot(
                as_of_date=forecast_date.date(),
                series_ids=[definition.series_id for definition in definitions],
            )
            if observations.empty:
                raise ValueError("The historical snapshot is empty.")

            bridge_dataset = build_bridge_dataset(
                observations=observations,
                definitions=definitions,
                target_series=target_series,
                target_period=target_period,
                data_as_of=forecast_date,
            )

            release_date = repository.initial_release_date(
                series_id=target_series,
                target_period=target_period,
            )
            if release_date is None:
                if is_recent_unreleased_period(target_period):
                    pending = {
                        "scope": "pending_outcome",
                        "forecast_date": forecast_date.date().isoformat(),
                        "target_period": str(target_period),
                        "reason": (
                            f"The initial release for {target_series} {target_period} "
                            "is not yet stored. It is excluded from evaluation until "
                            "an outcome becomes available."
                        ),
                    }
                    pending_outcomes.append(pending)
                    report(f"  pending outcome: {pending['reason']}")
                    continue
                raise ValueError(
                    f"No initial-release date is stored for {target_series} {target_period}."
                )

            release_timestamp = pd.Timestamp(release_date)
            ensure_snapshot(
                repository=repository,
                client=client,
                definition=target_definition,
                as_of_date=release_timestamp,
                refresh=config.refresh_snapshots,
                pause_seconds=config.request_pause_seconds,
            )
            actual_snapshot = repository.historical_snapshot(
                as_of_date=release_date,
                series_ids=[target_series],
            )
            actual = target_actual_from_snapshot(
                snapshot=actual_snapshot,
                target_definition=target_definition,
                target_period=target_period,
            )

            bridge = fit_bridge_ridge(
                bridge_dataset.training_frame,
                bridge_dataset.current_features,
                alpha=alpha,
                interval=interval,
            )
            ar1 = fit_ar1(bridge_dataset.training_frame["target"], interval=interval)
            period_results = [bridge, ar1]

            if config.include_legacy_ensembles:
                period_results.append(combine_equal_weight(bridge, ar1, interval=interval))

            if config.include_dfm:
                try:
                    mixed_dataset = build_mixed_frequency_dataset(
                        observations=observations,
                        definitions=definitions,
                        target_series=target_series,
                        target_period=target_period,
                        data_as_of=forecast_date,
                    )
                    dfm = fit_dynamic_factor(
                        dataset=mixed_dataset,
                        interval=interval,
                        factors=int(dfm_config.get("factors", 1)),
                        factor_orders=int(dfm_config.get("factor_orders", 1)),
                        idiosyncratic_ar1=bool(
                            dfm_config.get("idiosyncratic_ar1", True)
                        ),
                        maxiter=int(dfm_config.get("maxiter", 100)),
                        tolerance=float(dfm_config.get("tolerance", 1e-4)),
                        require_convergence=bool(
                            dfm_config.get("require_convergence", False)
                        ),
                    )
                    static_bridge_dfm = combine_weighted(
                        [bridge, dfm],
                        {"Bridge Ridge": 0.5, "Dynamic Factor Model": 0.5},
                        model_name="Bridge–DFM Ensemble",
                        interval=interval,
                        diagnostics={"weight_method": "equal"},
                    )
                    prior_results = pd.DataFrame(rows)
                    rolling_weights, weight_diagnostics = estimate_inverse_rmse_weights(
                        prior_results,
                        model_names=("Bridge Ridge", "Dynamic Factor Model"),
                        window=config.rolling_window,
                        min_history=config.rolling_min_history,
                        min_weight=config.rolling_min_weight,
                        max_weight=config.rolling_max_weight,
                    )
                    rolling_bridge_dfm = combine_weighted(
                        [bridge, dfm],
                        rolling_weights,
                        model_name="Rolling Bridge–DFM Ensemble",
                        interval=interval,
                        diagnostics=weight_diagnostics,
                    )
                    period_results.extend([dfm, static_bridge_dfm, rolling_bridge_dfm])

                    if config.include_legacy_ensembles:
                        period_results.append(
                            combine_equal_weight_many(
                                [bridge, ar1, dfm],
                                model_name="Three-model Ensemble",
                                interval=interval,
                            )
                        )

                    diagnostics_rows.extend(
                        [
                            {
                                "backtest_id": backtest_id,
                                "forecast_date": forecast_date.date(),
                                "target_period": str(target_period),
                                "model_name": dfm.model_name,
                                "status": "success",
                                "converged": bool(dfm.diagnostics.get("converged")),
                                "iterations": int(dfm.diagnostics.get("iterations", 0)),
                                "convergence_criterion": dfm.diagnostics.get(
                                    "convergence_criterion"
                                ),
                                "log_likelihood": dfm.diagnostics.get("log_likelihood"),
                                "details_json": json.dumps(dfm.diagnostics),
                                "created_at": created_at,
                            },
                            {
                                "backtest_id": backtest_id,
                                "forecast_date": forecast_date.date(),
                                "target_period": str(target_period),
                                "model_name": rolling_bridge_dfm.model_name,
                                "status": "success",
                                "converged": None,
                                "iterations": None,
                                "convergence_criterion": None,
                                "log_likelihood": None,
                                "details_json": json.dumps(
                                    rolling_bridge_dfm.diagnostics
                                ),
                                "created_at": created_at,
                            },
                        ]
                    )
                    report(
                        "  DFM completed; rolling weights="
                        + ", ".join(
                            f"{name}: {weight:.1%}"
                            for name, weight in rolling_weights.items()
                        )
                    )
                except Exception as exc:
                    failure = {
                        "scope": "model",
                        "forecast_date": forecast_date.date().isoformat(),
                        "target_period": str(target_period),
                        "model_name": "Dynamic Factor Model",
                        "reason": str(exc),
                    }
                    model_failures.append(failure)
                    diagnostics_rows.append(
                        {
                            "backtest_id": backtest_id,
                            "forecast_date": forecast_date.date(),
                            "target_period": str(target_period),
                            "model_name": "Dynamic Factor Model",
                            "status": "failed",
                            "converged": False,
                            "iterations": None,
                            "convergence_criterion": None,
                            "log_likelihood": None,
                            "details_json": json.dumps({"error": str(exc)}),
                            "created_at": created_at,
                        }
                    )
                    report(f"  DFM failed; Bridge and AR benchmarks retained: {exc}")

            for result in period_results:
                rows.append(
                    _result_row(
                        result=result,
                        backtest_id=backtest_id,
                        forecast_date=forecast_date,
                        target_period=target_period,
                        release_date=release_date,
                        actual=actual,
                        imputed_feature_count=(
                            0
                            if result.model_name == "Dynamic Factor Model"
                            else len(bridge_dataset.imputed_features)
                        ),
                        created_at=created_at,
                    )
                )

        except Exception as exc:
            skipped_quarters.append(
                {
                    "scope": "quarter",
                    "forecast_date": forecast_date.date().isoformat(),
                    "target_period": str(target_period),
                    "reason": str(exc),
                }
            )
            report(f"  quarter skipped: {exc}")

    results = pd.DataFrame(rows)
    diagnostics = pd.DataFrame(diagnostics_rows)
    metrics = calculate_backtest_metrics(results)
    regime_metrics = calculate_regime_metrics(results)
    issues = skipped_quarters + model_failures
    notices = pending_outcomes + issues
    status = "success" if not issues and not results.empty else (
        "partial" if not results.empty else "failed"
    )

    run_record = pd.DataFrame(
        [
            {
                "backtest_id": backtest_id,
                "created_at": created_at,
                "target_series": target_series,
                "start_date": pd.Timestamp(config.start_date).date(),
                "end_date": pd.Timestamp(config.end_date).date(),
                "forecast_frequency": "quarter_end",
                "status": status,
                "config_json": json.dumps(asdict(config)),
                "metrics_json": json.dumps(_metrics_to_dict(metrics)),
                "skipped_json": json.dumps(notices),
                "notes": (
                    "Quarter-end pseudo-real-time backtest using only FRED vintages "
                    "available on each forecast date. Initial GDP releases are the "
                    "evaluation outcomes. The production ensembles combine Bridge "
                    "Ridge and the DFM; rolling inverse-RMSE weights use only prior "
                    "completed quarters. AR(1) remains a benchmark and receives no "
                    "production weight. Recent unreleased outcomes are reported as "
                    "pending and do not make a run partial."
                ),
            }
        ]
    )

    repository.save_backtest_outputs(run_record, results, diagnostics)
    return {
        "backtest_id": backtest_id,
        "status": status,
        "results": results,
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "diagnostics": diagnostics,
        "skipped": issues,
        "notices": notices,
        "pending_outcomes": pending_outcomes,
        "skipped_quarters": skipped_quarters,
        "model_failures": model_failures,
    }

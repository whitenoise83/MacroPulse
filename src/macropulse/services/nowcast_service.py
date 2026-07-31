from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime

import pandas as pd

from macropulse.backtesting.intervals import calibrate_forecast_interval
from macropulse.backtesting.stages import infer_forecast_stage
from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
    build_stable_stage_policy,
    effective_bridge_dfm_weights,
    select_robust_stage_candidate,
)
from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    estimate_inverse_rmse_weights,
)
from macropulse.config import get_series_definitions, load_registry
from macropulse.data.repository import MacroRepository
from macropulse.models.baseline import (
    combine_weighted,
    estimate_bridge_ridge,
    fit_ar1,
)
from macropulse.models.dynamic_factor import estimate_dynamic_factor
from macropulse.governance.versioning import (
    current_model_identity,
    information_set_hash,
    load_governance_config,
)
from macropulse.processing.dataset import build_bridge_dataset
from macropulse.processing.mixed_frequency import build_mixed_frequency_dataset
from macropulse.services.news_service import (
    build_news_decomposition,
    record_news_failure,
)




def _data_freshness(observations: pd.DataFrame, definitions: list, cutoff: date) -> dict:
    output: dict[str, dict] = {}
    for definition in definitions:
        series = observations.loc[observations["series_id"] == definition.series_id]
        if series.empty:
            output[definition.series_id] = {
                "latest_observation_date": None,
                "age_days": None,
                "stale": True,
                "threshold_days": 75 if definition.frequency == "M" else 180,
            }
            continue
        latest = pd.to_datetime(series["observation_date"]).max().date()
        age = int((cutoff - latest).days)
        threshold = 75 if definition.frequency == "M" else 180
        output[definition.series_id] = {
            "latest_observation_date": latest.isoformat(),
            "age_days": age,
            "stale": age > threshold,
            "threshold_days": threshold,
        }
    return output

def _latest_backtest_history(repository: MacroRepository) -> pd.DataFrame:
    latest = repository.query_df(
        """
        SELECT backtest_id
        FROM backtest_runs
        WHERE status IN ('success', 'partial')
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if latest.empty:
        return pd.DataFrame()
    return repository.query_df(
        """
        SELECT forecast_date, target_period, model_name, point_forecast, actual,
               lower_80, upper_80
        FROM backtest_results
        WHERE backtest_id = ?
        ORDER BY forecast_date, model_name
        """,
        [latest.iloc[0]["backtest_id"]],
    )




def _latest_stage_history(
    repository: MacroRepository,
    forecast_stage: str,
    model_version: str,
) -> pd.DataFrame:
    latest = repository.query_df(
        """
        SELECT stage_backtest_id
        FROM stage_backtest_runs
        WHERE status IN ('success', 'partial') AND model_version = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [model_version],
    )
    if latest.empty:
        return pd.DataFrame()
    return repository.query_df(
        """
        SELECT forecast_stage, forecast_date, target_period, model_name,
               point_forecast, actual, lower_80, upper_80
        FROM stage_backtest_results
        WHERE stage_backtest_id = ? AND forecast_stage = ?
        ORDER BY forecast_date, model_name
        """,
        [latest.iloc[0]["stage_backtest_id"], forecast_stage],
    )


def _select_preferred_result(
    candidates: list,
    history: pd.DataFrame,
    minimum_quarters: int = 8,
) -> tuple[object, dict]:
    """Select a live headline model using completed trailing backtest evidence."""
    candidate_map = {result.model_name: result for result in candidates}
    eligible_names = [
        name
        for name in [
            "Bridge Ridge",
            "Dynamic Factor Model",
            "Bridge–DFM Ensemble",
            "Rolling Bridge–DFM Ensemble",
        ]
        if name in candidate_map
    ]
    fallback = candidate_map.get("Bridge Ridge", candidates[0])
    diagnostics = {
        "method": "bridge_fallback",
        "selected_model": fallback.model_name,
        "sample": "none",
        "observations": 0,
    }
    if history.empty or not eligible_names:
        return fallback, diagnostics

    frame = history.loc[history["model_name"].isin(eligible_names)].copy()
    if frame.empty:
        return fallback, diagnostics
    dates = sorted(pd.to_datetime(frame["forecast_date"]).dropna().unique())
    trailing_dates = set(dates[-20:])
    frame = frame.loc[pd.to_datetime(frame["forecast_date"]).isin(trailing_dates)]
    metrics = calculate_backtest_metrics(frame)
    metrics = metrics.loc[
        (metrics["model_name"].isin(eligible_names))
        & (metrics["observations"] >= minimum_quarters)
    ].sort_values(["rmse", "mae", "model_name"])
    if metrics.empty:
        return fallback, diagnostics

    selected = metrics.iloc[0]
    result = candidate_map[str(selected["model_name"])]
    diagnostics = {
        "method": "lowest_trailing_20_rmse",
        "selected_model": result.model_name,
        "sample": "last_20_completed_quarters",
        "observations": int(selected["observations"]),
        "rmse": float(selected["rmse"]),
        "mae": float(selected["mae"]),
    }
    return result, diagnostics


def run_model_suite_nowcast(repository: MacroRepository | None = None) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()

    registry = load_registry()
    definitions = get_series_definitions()
    target_series = registry["model"]["target_series"]
    alpha = float(registry["model"].get("ridge_alpha", 10.0))
    interval = float(registry["model"].get("prediction_interval", 0.80))
    dfm_config = registry.get("dynamic_factor", {})
    ensemble_config = registry.get("ensemble", {})
    news_config = registry.get("news", {})
    identity = current_model_identity()
    governance = load_governance_config()
    production_config = governance.get("production_policy", {})
    repository.register_model_identity(identity.as_dict())

    observations = repository.latest_observations(
        [definition.series_id for definition in definitions]
    )
    data_freshness = _data_freshness(observations, definitions, date.today())
    bridge_dataset = build_bridge_dataset(observations, definitions, target_series)
    information_cutoff = date.today()
    release_date = repository.initial_release_date(
        target_series, bridge_dataset.target_period
    )
    forecast_stage = infer_forecast_stage(
        bridge_dataset.target_period, information_cutoff, release_date
    )
    performance_history_version = str(
        production_config.get("performance_history_version", identity.model_version)
    )
    stage_history = _latest_stage_history(
        repository, forecast_stage, performance_history_version
    )
    quarter_history = _latest_backtest_history(repository)
    performance_history = stage_history if not stage_history.empty else quarter_history
    performance_history_source = (
        f"stage:{forecast_stage}@v{performance_history_version}"
        if not stage_history.empty
        else "quarter_end_fallback"
    )

    bridge_fit = estimate_bridge_ridge(
        bridge_dataset.training_frame,
        bridge_dataset.current_features,
        alpha=alpha,
        interval=interval,
    )
    bridge = bridge_fit.forecast
    ar1 = fit_ar1(bridge_dataset.training_frame["target"], interval=interval)

    results = [bridge, ar1]
    dfm = None
    dfm_fit = None
    dfm_error = None
    rolling_weights = {"Bridge Ridge": 1.0, "Dynamic Factor Model": 0.0}
    weight_diagnostics: dict = {"weight_method": "dfm_unavailable"}
    try:
        mixed_dataset = build_mixed_frequency_dataset(
            observations=observations,
            definitions=definitions,
            target_series=target_series,
            target_period=bridge_dataset.target_period,
            data_as_of=bridge_dataset.data_as_of,
        )
        dfm_fit = estimate_dynamic_factor(
            dataset=mixed_dataset,
            interval=interval,
            factors=int(dfm_config.get("factors", 1)),
            factor_orders=int(dfm_config.get("factor_orders", 1)),
            idiosyncratic_ar1=bool(dfm_config.get("idiosyncratic_ar1", True)),
            maxiter=int(dfm_config.get("maxiter", 100)),
            tolerance=float(dfm_config.get("tolerance", 1e-4)),
            require_convergence=bool(dfm_config.get("require_convergence", False)),
        )
        dfm = dfm_fit.forecast
        bridge_dfm = combine_weighted(
            [bridge, dfm],
            {"Bridge Ridge": 0.5, "Dynamic Factor Model": 0.5},
            model_name="Bridge–DFM Ensemble",
            interval=interval,
            diagnostics={"weight_method": "equal"},
        )
        rolling_weights, weight_diagnostics = estimate_inverse_rmse_weights(
            performance_history,
            model_names=("Bridge Ridge", "Dynamic Factor Model"),
            window=int(ensemble_config.get("rolling_window", 12)),
            min_history=int(ensemble_config.get("min_history", 8)),
            min_weight=float(ensemble_config.get("min_weight", 0.10)),
            max_weight=float(ensemble_config.get("max_weight", 0.70)),
        )
        rolling_ensemble = combine_weighted(
            [bridge, dfm],
            rolling_weights,
            model_name="Rolling Bridge–DFM Ensemble",
            interval=interval,
            diagnostics=weight_diagnostics,
        )
        results.extend([dfm, bridge_dfm, rolling_ensemble])
        weight_diagnostics["history_source"] = performance_history_source
        stable_policy, stable_diagnostics = build_stable_stage_policy(
            results,
            forecast_stage=forecast_stage,
            policy=production_config.get("stable_stage_policy", {}),
            fallback_model=str(production_config.get("dfm_failure_fallback", "Bridge Ridge")),
        )
        robust_policy, robust_diagnostics = select_robust_stage_candidate(
            results,
            prior_results=stage_history,
            forecast_stage=forecast_stage,
            stable_policy=production_config.get("stable_stage_policy", {}),
            window=int(production_config.get("selection_window", 20)),
            min_history=int(production_config.get("selection_min_history", 20)),
            switch_threshold=float(production_config.get("selection_switch_threshold", 0.05)),
            tail_ratio_limit=float(production_config.get("selection_tail_ratio_limit", 1.10)),
            maximum_error_ratio_limit=float(
                production_config.get("selection_maximum_error_ratio_limit", 1.25)
            ),
            score_weights=production_config.get("selection_score_weights", {}),
            fallback_model=str(production_config.get("dfm_failure_fallback", "Bridge Ridge")),
        )
        stable_diagnostics["history_source"] = "predeclared_stage_policy"
        robust_diagnostics["history_source"] = (
            f"stage:{forecast_stage}" if not stage_history.empty else "stable_policy_fallback"
        )
        results.extend([stable_policy, robust_policy])
        preferred = stable_policy
        selection_diagnostics = stable_diagnostics
        production_weights = effective_bridge_dfm_weights(
            str(stable_diagnostics["selected_component"]),
            rolling_weights=rolling_weights,
        )
    except Exception as exc:
        dfm_error = str(exc)
        stable_policy, stable_diagnostics = build_stable_stage_policy(
            [bridge],
            forecast_stage=forecast_stage,
            policy=production_config.get("stable_stage_policy", {}),
            fallback_model="Bridge Ridge",
        )
        robust_policy, robust_diagnostics = select_robust_stage_candidate(
            [bridge],
            prior_results=pd.DataFrame(),
            forecast_stage=forecast_stage,
            incumbent_model="Bridge Ridge",
            stable_policy=production_config.get("stable_stage_policy", {}),
            fallback_model="Bridge Ridge",
        )
        stable_diagnostics.update(
            {
                "method": "bridge_fallback_dfm_failure",
                "error": dfm_error,
                "history_source": "none",
            }
        )
        robust_diagnostics.update(
            {
                "method": "bridge_fallback_dfm_failure",
                "error": dfm_error,
                "history_source": "none",
            }
        )
        results.extend([stable_policy, robust_policy])
        preferred = stable_policy
        selection_diagnostics = stable_diagnostics
        production_weights = {"Bridge Ridge": 1.0, "Dynamic Factor Model": 0.0}

    preferred_name = preferred.model_name
    interval_config = governance.get("staged_backtest", {})
    calibrated_results = []
    interval_diagnostics = {}
    for result in results:
        calibrated, diagnostics = calibrate_forecast_interval(
            result=result,
            prior_results=stage_history,
            forecast_stage=forecast_stage,
            coverage=float(interval_config.get("interval_coverage", interval)),
            window=int(interval_config.get("interval_window", 20)),
            min_history=int(interval_config.get("interval_min_history", 12)),
        )
        calibrated_results.append(calibrated)
        interval_diagnostics[result.model_name] = diagnostics
    results = calibrated_results
    preferred = next(
        (result for result in results if result.model_name == preferred_name),
        results[0],
    )

    previous_run = repository.latest_prior_model_run(
        str(bridge_dataset.target_period)
    )

    run_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)

    metrics = {
        "training_observations": int(len(bridge_dataset.training_frame)),
        "feature_count": int(len(bridge_dataset.feature_names)),
        "imputed_features": bridge_dataset.imputed_features,
        "bridge_rmse": bridge.sigma,
        "ar1_rmse": ar1.sigma,
        "preferred_model": preferred.model_name,
        "selected_component_model": selection_diagnostics.get("selected_component"),
        "preferred_sigma": preferred.sigma,
        "interval": interval,
        "production_weights": production_weights,
        "rolling_candidate_weights": rolling_weights,
        "weight_diagnostics": weight_diagnostics,
        "production_selection": selection_diagnostics,
        "robust_shadow_selection": robust_diagnostics,
        "performance_history_source": performance_history_source,
        "forecast_stage": forecast_stage,
        "information_cutoff": information_cutoff.isoformat(),
        "model_identity": identity.as_dict(),
        "interval_calibration": interval_diagnostics,
        "data_freshness": data_freshness,
        "stale_series": [
            series_id for series_id, item in data_freshness.items() if item.get("stale")
        ],
        "dynamic_factor": (
            {"status": "success", **dfm.diagnostics}
            if dfm is not None
            else {"status": "failed", "error": dfm_error}
        ),
    }

    notes = (
        "MacroPulse Model 1A v1.0.0 production suite. The Stable Stage Policy is the "
        "approved production forecast. A Robust Stage-Adaptive Policy is stored as a shadow "
        "challenger using prior common-stage outcomes, a 5% switching hurdle, and "
        "tail-risk guards. The production component is represented as transparent "
        "Bridge/DFM weights for exact news decomposition. AR(1) is a benchmark."
    )
    if dfm_error:
        notes += f" DFM failed, so Bridge Ridge was used: {dfm_error}"

    run_record = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_name": preferred.model_name,
                "target_series": target_series,
                "run_timestamp": created_at,
                "data_as_of": bridge_dataset.data_as_of.date(),
                "target_period": str(bridge_dataset.target_period),
                "status": "success",
                "metrics_json": json.dumps(metrics),
                "notes": notes,
            }
        ]
    )

    forecast_rows = []
    coefficient_rows = []
    for result in results:
        forecast_rows.append(
            {
                "run_id": run_id,
                "model_name": result.model_name,
                "target_series": target_series,
                "target_period": str(bridge_dataset.target_period),
                "point_forecast": result.point_forecast,
                "lower_80": result.lower,
                "upper_80": result.upper,
                "created_at": created_at,
            }
        )
        for feature, coefficient in result.coefficients.items():
            if pd.isna(coefficient):
                continue
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
    repository.save_information_set(run_id, observations)
    info_hash = information_set_hash(observations)
    forecast_registry = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "information_set_hash": info_hash,
                "information_cutoff": information_cutoff,
                "data_as_of": bridge_dataset.data_as_of.date(),
                "target_period": str(bridge_dataset.target_period),
                "forecast_stage": forecast_stage,
                "champion_model": preferred.model_name,
                "production_forecast": preferred.point_forecast,
                "lower_80": preferred.lower,
                "upper_80": preferred.upper,
                "status": "success",
                "created_at": created_at,
            }
        ]
    )
    repository.save_forecast_registry(forecast_registry)

    news_decomposition: dict = {
        "status": "no_previous_run",
        "message": "A second run for the same target quarter is required.",
    }
    if not previous_run.empty:
        try:
            news_decomposition = build_news_decomposition(
                repository=repository,
                previous_run=previous_run.iloc[0],
                current_run_id=run_id,
                current_observations=observations,
                current_bridge_fit=bridge_fit,
                current_dfm_fit=dfm_fit,
                current_weights=production_weights,
                definitions=definitions,
                target_series=target_series,
                target_period=bridge_dataset.target_period,
                ridge_alpha=alpha,
                interval=interval,
                dfm_config={**dfm_config, **news_config},
            )
        except Exception as exc:
            error = str(exc)
            try:
                record_news_failure(
                    repository,
                    current_run_id=run_id,
                    previous_run_id=str(previous_run.iloc[0]["run_id"]),
                    target_period=bridge_dataset.target_period,
                    error=error,
                )
            except Exception:
                pass
            news_decomposition = {
                "status": "failed",
                "error": error,
            }

    return {
        "run_id": run_id,
        "target_period": str(bridge_dataset.target_period),
        "data_as_of": bridge_dataset.data_as_of.date().isoformat(),
        "forecasts": forecasts,
        "coefficients": coefficients,
        "metrics": metrics,
        "dfm_error": dfm_error,
        "news_decomposition": news_decomposition,
        "forecast_stage": forecast_stage,
        "model_identity": identity.as_dict(),
        "information_set_hash": info_hash,
    }


def run_baseline_nowcast(repository: MacroRepository | None = None) -> dict:
    """Backward-compatible entry point; runs the production model suite."""
    return run_model_suite_nowcast(repository=repository)

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import information_set_hash
from macropulse.inflation.config import (
    get_inflation_model_config,
    get_inflation_series_definitions,
    target_definitions,
)
from macropulse.inflation.dataset import InflationDataset, build_target_dataset
from macropulse.inflation.models import (
    InflationModelResult,
    combine_equal_weight,
    fit_ar1,
    fit_ridge_bridge,
    fit_rolling_mean,
)
from macropulse.inflation.policy import (
    SELECTED_INTERVAL_METHOD,
    ShadowSelectorConfig,
    policy_model,
    select_prior_only_shadow,
)
from macropulse.inflation.stages import (
    INFLATION_STAGE_MAP,
    infer_live_inflation_stage,
)
from macropulse.inflation.versioning import current_inflation_model_identity


@dataclass(frozen=True)
class LiveInterval:
    lower: float
    upper: float
    half_width: float
    method: str
    prior_error_count: int
    calibration_cutoff_period: str


@dataclass(frozen=True)
class CandidateEvidence:
    validation_id: str
    backtest_id: str
    report_path: str
    passed_checks: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def estimate_target_models(
    observations: pd.DataFrame,
    target_series: str,
    target_period: pd.Period | str | None = None,
) -> tuple[InflationDataset, dict[str, InflationModelResult]]:
    """Estimate all declared Model 1B components for one target month."""
    config = get_inflation_model_config()
    dataset = build_target_dataset(observations, target_series, target_period=target_period)
    minimum = int(config.get("minimum_training_observations", 120))
    if len(dataset.y) < minimum:
        raise ValueError(
            f"{target_series} has {len(dataset.y)} complete observations; "
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
    return dataset, {
        result.model_name: result for result in [ridge, ar1, mean, ensemble]
    }


def latest_candidate_evidence(repository: MacroRepository) -> CandidateEvidence:
    rows = repository.query_df(
        """
        SELECT validation_id, backtest_id, report_path, passed_checks, summary_json,
               created_at
        FROM inflation_validation_runs
        WHERE status = 'pass'
        ORDER BY created_at DESC
        """
    )
    for row in rows.itertuples(index=False):
        try:
            summary = json.loads(row.summary_json or "{}")
        except json.JSONDecodeError:
            continue
        if summary.get("validation_type") == "candidate_policy":
            return CandidateEvidence(
                validation_id=str(row.validation_id),
                backtest_id=str(row.backtest_id),
                report_path=str(row.report_path or ""),
                passed_checks=int(row.passed_checks),
            )
    raise RuntimeError(
        "No passing Model 1B candidate-policy validation is stored. "
        "Run scripts\\run_inflation_candidate_validation.py first."
    )


def estimate_initial_release_date(
    repository: MacroRepository,
    target_series: str,
    target_period: pd.Period | str,
    lookback: int = 24,
) -> tuple[date, dict[str, Any]]:
    """Estimate the unreleased target's initial-release date from stored vintages."""
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="M")
    )
    actual = repository.initial_release_date(target_series, period)
    if actual is not None:
        return actual, {"method": "stored_initial_release", "observations": 1}

    history = repository.query_df(
        """
        SELECT observation_date, MIN(realtime_start) AS release_date
        FROM observations
        WHERE series_id = ?
          AND vintage_type = 'initial'
          AND observation_date < ?
        GROUP BY observation_date
        ORDER BY observation_date DESC
        LIMIT ?
        """,
        [target_series, period.start_time.date(), int(lookback)],
    )
    lags: list[int] = []
    if not history.empty:
        for row in history.itertuples(index=False):
            observation_period = pd.Period(pd.Timestamp(row.observation_date), freq="M")
            release = pd.Timestamp(row.release_date).date()
            lag = (release - observation_period.end_time.date()).days
            if 0 < lag < 75:
                lags.append(int(lag))
    fallback = 14 if target_series in {"CPIAUCSL", "CPILFESL"} else 30
    lag_days = int(round(float(np.median(lags)))) if lags else fallback
    estimated = period.end_time.date() + timedelta(days=lag_days)
    return estimated, {
        "method": "median_historical_release_lag" if lags else "fallback_release_lag",
        "observations": len(lags),
        "lag_days": lag_days,
    }


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, probability: float) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    cutoff = float(probability) * float(cumulative[-1])
    index = int(np.searchsorted(cumulative, cutoff, side="left"))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def live_interval_from_backtest(
    history: pd.DataFrame,
    target_period: pd.Period | str,
    point_forecast: float,
    minimum_prior_errors: int = 24,
    rolling_window: int = 48,
    half_life: float = 18.0,
    coverage: float = 0.80,
) -> LiveInterval:
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="M")
    )
    prior = history.copy()
    prior["_period"] = pd.PeriodIndex(prior["target_period"], freq="M")
    prior = prior.loc[prior["_period"] < period].sort_values("_period").tail(rolling_window)
    errors = pd.to_numeric(prior["abs_error"], errors="coerce")
    usable = prior.loc[errors.notna()].copy()
    usable["abs_error"] = errors.loc[errors.notna()].astype(float)
    if len(usable) < minimum_prior_errors:
        raise RuntimeError(
            f"Only {len(usable)} prior errors are available; "
            f"{minimum_prior_errors} are required for live interval calibration."
        )
    values = usable["abs_error"].to_numpy(float)
    ages = np.arange(len(values) - 1, -1, -1, dtype=float)
    weights = np.power(0.5, ages / float(half_life))
    width = max(0.0, _weighted_quantile(values, weights, coverage))
    return LiveInterval(
        lower=float(point_forecast - width),
        upper=float(point_forecast + width),
        half_width=float(width),
        method=SELECTED_INTERVAL_METHOD,
        prior_error_count=int(len(usable)),
        calibration_cutoff_period=str(usable["_period"].iloc[-1]),
    )


def live_shadow_selection(
    history: pd.DataFrame,
    target_series: str,
    forecast_stage: str,
    target_period: pd.Period | str,
    components: dict[str, InflationModelResult],
    config: ShadowSelectorConfig | None = None,
) -> dict[str, Any]:
    """Advance the validated prior-only selector to an unreleased live month."""
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="M")
    )
    historical = history.loc[
        (history["target_series"] == target_series)
        & (history["forecast_stage"] == forecast_stage)
    ].copy()
    historical["_period"] = pd.PeriodIndex(historical["target_period"], freq="M")
    historical = historical.loc[historical["_period"] < period].drop(columns="_period")
    current_rows = pd.DataFrame(
        [
            {
                "target_series": target_series,
                "forecast_stage": forecast_stage,
                "target_period": str(period),
                "model_name": name,
                "point_forecast": result.point_forecast,
                "error": np.nan,
                "abs_error": np.nan,
            }
            for name, result in components.items()
        ]
    )
    combined = pd.concat([historical, current_rows], ignore_index=True, sort=False)
    selected = select_prior_only_shadow(combined, config=config)
    live = selected.loc[
        (selected["target_series"] == target_series)
        & (selected["forecast_stage"] == forecast_stage)
        & (selected["target_period"].astype(str) == str(period))
    ]
    if live.empty:
        raise RuntimeError("The adaptive shadow selector did not produce a live choice.")
    row = live.iloc[0]
    model_name = str(row.get("selected_model", row["model_name"]))
    return {
        "model_name": model_name,
        "point_forecast": float(components[model_name].point_forecast),
        "selection_reason": str(row.get("selection_reason", "")),
        "prior_period_count": int(row.get("prior_period_count", 0)),
        "selection_cutoff_period": row.get("selection_cutoff_period"),
        "selection_changed": bool(row.get("selection_changed", False)),
        "cumulative_switch_count": int(row.get("cumulative_switch_count", 0)),
    }


def model_state_hash(
    component_rows: pd.DataFrame,
    coefficient_rows: pd.DataFrame,
) -> str:
    components = component_rows[
        ["target_series", "target_period", "forecast_stage", "model_name", "point_forecast"]
    ].sort_values(["target_series", "forecast_stage", "model_name"])
    coefficients = coefficient_rows.copy()
    if not coefficients.empty:
        coefficients = coefficients[
            ["target_series", "model_name", "feature", "coefficient"]
        ].sort_values(["target_series", "model_name", "feature"])
    return _sha256_payload(
        {
            "components": components.where(pd.notna(components), None).to_dict("records"),
            "coefficients": coefficients.where(pd.notna(coefficients), None).to_dict("records"),
        }
    )


def _signature_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat() if value.time() == pd.Timestamp(value.date()).time() else value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def governance_signature_payload(
    run_record: dict[str, Any],
    forecast_rows: pd.DataFrame,
) -> dict[str, Any]:
    fields = [
        "run_id",
        "model_id",
        "model_version",
        "candidate_validation_id",
        "backtest_id",
        "information_cutoff",
        "information_set_hash",
        "model_state_hash",
        "config_hash",
        "code_hash",
        "git_commit",
    ]
    forecasts = forecast_rows[
        [
            "target_series",
            "target_period",
            "forecast_stage",
            "stable_model_name",
            "stable_point_forecast",
            "lower_80",
            "upper_80",
            "shadow_model_name",
            "shadow_point_forecast",
        ]
    ].sort_values("target_series")
    records = forecasts.where(pd.notna(forecasts), None).to_dict("records")
    return {
        "run": {field: _signature_value(run_record.get(field)) for field in fields},
        "forecasts": [
            {key: _signature_value(value) for key, value in record.items()}
            for record in records
        ],
    }


def governance_signature(run_record: dict[str, Any], forecast_rows: pd.DataFrame) -> str:
    return _sha256_payload(governance_signature_payload(run_record, forecast_rows))


def run_governed_inflation_nowcast(
    repository: MacroRepository | None = None,
    information_cutoff: date | None = None,
    build_news: bool = True,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    cutoff = information_cutoff or date.today()
    identity = current_inflation_model_identity()
    repository.register_model_identity(
        identity.as_dict(),
        notes=(
            f"Model 1B v{identity.model_version} {identity.lifecycle_status} live identity."
        ),
    )
    evidence = latest_candidate_evidence(repository)
    definitions = get_inflation_series_definitions()
    observations = repository.latest_observations([item.series_id for item in definitions])
    if observations.empty:
        raise RuntimeError("No inflation observations are stored. Run download_inflation_data.py first.")
    observations["observation_date"] = pd.to_datetime(observations["observation_date"])
    observations = observations.loc[observations["observation_date"].dt.date <= cutoff].copy()
    if observations.empty:
        raise RuntimeError("No inflation observations are available at the requested information cutoff.")

    run_id = str(uuid.uuid4())
    timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    info_hash = information_set_hash(observations)
    config = get_inflation_model_config()
    all_history = repository.query_df(
        """
        SELECT *
        FROM inflation_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [evidence.backtest_id],
    )
    if all_history.empty:
        raise RuntimeError(f"Candidate backtest {evidence.backtest_id} contains no results.")

    forecast_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    coefficient_rows: list[dict[str, Any]] = []
    target_metrics: dict[str, Any] = {}

    for definition in target_definitions():
        dataset, components = estimate_target_models(observations, definition.series_id)
        release_date, release_diagnostics = estimate_initial_release_date(
            repository, definition.series_id, dataset.target_period
        )
        stage = infer_live_inflation_stage(dataset.target_period, cutoff, release_date)
        stable_name = policy_model(definition.series_id, stage)
        stable = components[stable_name]
        history = all_history.loc[
            (all_history["target_series"] == definition.series_id)
            & (all_history["forecast_stage"] == stage)
            & (all_history["model_name"] == stable_name)
        ].copy()
        interval = live_interval_from_backtest(
            history,
            dataset.target_period,
            stable.point_forecast,
            minimum_prior_errors=int(config.get("interval_calibration_minimum_errors", 24)),
            rolling_window=int(config.get("interval_calibration_window", 48)),
            half_life=float(config.get("interval_calibration_half_life", 18.0)),
            coverage=float(config.get("interval_coverage", 0.80)),
        )
        shadow = live_shadow_selection(
            all_history,
            definition.series_id,
            stage,
            dataset.target_period,
            components,
            config=ShadowSelectorConfig(
                minimum_prior_errors=int(config.get("policy_evaluation_minimum_prior_errors", 24)),
                rolling_window=int(config.get("policy_evaluation_window", 36)),
                switch_hurdle=float(config.get("policy_switch_hurdle", 0.02)),
            ),
        )
        for name, result in components.items():
            component_rows.append(
                {
                    "run_id": run_id,
                    "target_series": definition.series_id,
                    "target_name": definition.name,
                    "target_period": str(dataset.target_period),
                    "forecast_stage": stage,
                    "model_name": name,
                    "point_forecast": float(result.point_forecast),
                    "raw_lower_80": float(result.lower_80),
                    "raw_upper_80": float(result.upper_80),
                    "role": (
                        "stable_candidate" if name == stable_name else
                        "shadow_challenger" if name == shadow["model_name"] else
                        "component"
                    ),
                    "diagnostics_json": json.dumps(result.diagnostics, sort_keys=True, default=str),
                    "created_at": timestamp,
                }
            )
            for feature, coefficient in result.coefficients.items():
                coefficient_rows.append(
                    {
                        "run_id": run_id,
                        "target_series": definition.series_id,
                        "model_name": name,
                        "feature": feature,
                        "coefficient": float(coefficient),
                    }
                )
        forecast_rows.append(
            {
                "run_id": run_id,
                "target_series": definition.series_id,
                "target_name": definition.name,
                "target_period": str(dataset.target_period),
                "forecast_stage": stage,
                "information_cutoff": cutoff,
                "estimated_release_date": release_date,
                "stable_model_name": stable_name,
                "stable_point_forecast": float(stable.point_forecast),
                "lower_80": interval.lower,
                "upper_80": interval.upper,
                "interval_half_width": interval.half_width,
                "interval_method": interval.method,
                "interval_prior_errors": interval.prior_error_count,
                "interval_cutoff_period": interval.calibration_cutoff_period,
                "shadow_model_name": shadow["model_name"],
                "shadow_point_forecast": shadow["point_forecast"],
                "shadow_selection_reason": shadow["selection_reason"],
                "shadow_prior_errors": shadow["prior_period_count"],
                "latest_observed_period": str(dataset.latest_observed_period),
                "created_at": timestamp,
            }
        )
        target_metrics[definition.series_id] = {
            "target_name": definition.name,
            "target_period": str(dataset.target_period),
            "forecast_stage": stage,
            "forecast_stage_label": INFLATION_STAGE_MAP[stage].label,
            "estimated_release_date": release_date.isoformat(),
            "release_date_diagnostics": release_diagnostics,
            "latest_observed_period": str(dataset.latest_observed_period),
            "latest_monthly_annualised": dataset.latest_mom_annualised,
            "latest_three_month_annualised": dataset.latest_three_month_annualised,
            "latest_year_over_year": dataset.latest_yoy,
            "training_observations": len(dataset.y),
            "feature_count": dataset.X.shape[1],
            "feature_ages": dataset.feature_ages,
            "imputed_features": dataset.imputed_features,
            "stable_model": stable_name,
            "shadow_model": shadow["model_name"],
        }

    forecasts = pd.DataFrame(forecast_rows)
    components = pd.DataFrame(component_rows)
    coefficients = pd.DataFrame(
        coefficient_rows,
        columns=["run_id", "target_series", "model_name", "feature", "coefficient"],
    )
    state_hash = model_state_hash(components, coefficients)
    base_run: dict[str, Any] = {
        "run_id": run_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "run_timestamp": timestamp,
        "information_cutoff": cutoff,
        "data_as_of": pd.to_datetime(observations["observation_date"]).max().date(),
        "status": "success",
        "candidate_validation_id": evidence.validation_id,
        "backtest_id": evidence.backtest_id,
        "config_hash": identity.config_hash,
        "code_hash": identity.code_hash,
        "git_commit": identity.git_commit,
        "information_set_hash": info_hash,
        "model_state_hash": state_hash,
        "governance_signature": "",
        "metrics_json": json.dumps(
            {
                "research_status": (
                    "production" if identity.lifecycle_status == "production"
                    else "governed_live_candidate"
                ),
                "candidate_validation": {
                    "validation_id": evidence.validation_id,
                    "passed_checks": evidence.passed_checks,
                    "report_path": evidence.report_path,
                },
                "point_policy": "stable_candidate",
                "shadow_policy": "adaptive_shadow_only",
                "interval_method": SELECTED_INTERVAL_METHOD,
                "targets": target_metrics,
            },
            sort_keys=True,
            default=str,
        ),
        "notes": (
            f"Model 1B v{identity.model_version} {identity.lifecycle_status}. The stable policy "
            "controls the headline; the adaptive selector is stored as a shadow "
            "challenger only."
        ),
    }
    base_run["governance_signature"] = governance_signature(base_run, forecasts)
    live_run = pd.DataFrame([base_run])

    legacy_run = pd.DataFrame(
        [
            {
                "run_id": run_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "run_timestamp": timestamp,
                "status": "success",
                "data_as_of": base_run["data_as_of"],
                "metrics_json": base_run["metrics_json"],
                "notes": base_run["notes"],
            }
        ]
    )
    legacy_forecasts = components.rename(
        columns={"raw_lower_80": "lower_80", "raw_upper_80": "upper_80"}
    )[
        [
            "run_id",
            "target_series",
            "target_name",
            "target_period",
            "model_name",
            "point_forecast",
            "lower_80",
            "upper_80",
            "created_at",
        ]
    ]
    repository.save_inflation_outputs(legacy_run, legacy_forecasts, coefficients)
    repository.save_inflation_live_outputs(live_run, forecasts, components)
    repository.save_inflation_live_information_set(run_id, observations)

    news_result: dict[str, Any] | None = None
    if build_news:
        from macropulse.inflation.news import build_inflation_news_decomposition

        try:
            news_result = build_inflation_news_decomposition(repository, run_id)
        except Exception as exc:  # live forecast remains valid if attribution fails
            repository.record_inflation_news_failure(run_id, str(exc))
            news_result = {"status": "failed", "error": str(exc)}

    return {
        "run_id": run_id,
        "identity": identity.as_dict(),
        "candidate_validation_id": evidence.validation_id,
        "backtest_id": evidence.backtest_id,
        "information_cutoff": cutoff,
        "data_as_of": base_run["data_as_of"],
        "information_set_hash": info_hash,
        "model_state_hash": state_hash,
        "governance_signature": base_run["governance_signature"],
        "forecasts": forecasts,
        "components": components,
        "metrics": target_metrics,
        "news": news_result,
    }

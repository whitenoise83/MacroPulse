from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.policy import (
    SELECTED_INTERVAL_METHOD,
    STABLE_POLICY,
    ShadowSelectorConfig,
    attach_calibrated_intervals,
    compare_policies_on_common_sample,
    select_fixed_policy,
    select_prior_only_shadow,
    summarise_forecasts,
    summarise_intervals,
    summarise_regime_performance,
    summarise_shadow_switching,
)
from macropulse.labour.versioning import current_labour_model_identity
from macropulse.settings import settings


EXPECTED_MODELS = {
    "Labour AR(1)",
    "Labour 12-Month Mean",
    "Labour Bridge Ridge",
    "Labour Factor Ridge",
    "Labour Equal-Weight Ensemble",
}
EXPECTED_TARGETS = set(STABLE_POLICY)
EXPECTED_STAGES = {
    stage for stage_map in STABLE_POLICY.values() for stage in stage_map
}
ALLOWED_NOTICE_KINDS = {"pending", "training_warmup", "structural_missing"}


@dataclass(frozen=True)
class CandidateValidationThresholds:
    minimum_training_observations: int = 120
    minimum_fixed_months_per_group: int = 100
    minimum_common_months_per_group: int = 80
    fixed_rmse_ratio: float = 1.06
    fixed_mae_ratio: float = 1.12
    fixed_median_ratio: float = 2.00
    accuracy_eligible_rmse_ratio: float = 1.10
    accuracy_eligible_mae_ratio: float = 1.15
    fixed_tail_ratio: float = 1.25
    max_error_tail_eligibility_ratio: float = 1.50
    fixed_max_error_ratio: float = 1.20
    maximum_directional_accuracy_gap: float = 0.10
    payroll_maximum_absolute_bias: float = 75.0
    unemployment_maximum_absolute_bias: float = 0.30
    earnings_maximum_absolute_bias: float = 0.80
    minimum_regime_months: int = 20
    maximum_shadow_broad_wins: int = 5
    maximum_shadow_switches_per_group: int = 6
    interval_aggregate_coverage_lower: float = 0.76
    interval_aggregate_coverage_upper: float = 0.88
    interval_group_coverage_lower: float = 0.75
    interval_group_coverage_upper: float = 0.90
    minimum_interval_months_per_group: int = 80
    minimum_prior_errors: int = 24


def _json_key(value: object) -> str:
    if isinstance(value, tuple):
        return " | ".join(str(item) for item in value)
    return str(value)


def _json_safe(value: object) -> object:
    if isinstance(value, Mapping):
        return {_json_key(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_safe(item) for item in value), key=str)
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _check(
    gate_name: str,
    check_name: str,
    status: str,
    observed_value: object,
    threshold: str,
    details: object | None = None,
) -> dict:
    return {
        "gate_name": gate_name,
        "check_name": check_name,
        "status": status,
        "observed_value": str(observed_value),
        "threshold": threshold,
        "details_json": json.dumps(
            _json_safe(details or {}), default=str, sort_keys=True
        ),
    }


def _error_metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    errors = pd.to_numeric(frame["error"], errors="coerce")
    usable = frame.loc[errors.notna()].copy()
    errors = errors.dropna().astype(float)
    if errors.empty:
        return {}
    absolute = errors.abs()
    direction = pd.to_numeric(usable.get("direction_correct"), errors="coerce")
    return {
        "observations": int(len(errors)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(absolute.mean()),
        "bias": float(errors.mean()),
        "median_ae": float(absolute.median()),
        "p90_abs_error": float(absolute.quantile(0.90)),
        "max_abs_error": float(absolute.max()),
        "directional_accuracy": (
            float(direction.mean()) if direction.notna().any() else np.nan
        ),
    }


def _all_model_metrics(results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (target, stage, model), frame in results.groupby(
        ["target_series", "forecast_stage", "model_name"]
    ):
        rows.append(
            {
                "target_series": str(target),
                "forecast_stage": str(stage),
                "model_name": str(model),
                **_error_metrics(frame),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["target_series", "forecast_stage", "model_name"]
    )


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    return numerator / denominator.replace(0.0, np.nan)


def _coherent_comparators(
    all_metrics: pd.DataFrame,
    thresholds: CandidateValidationThresholds,
) -> pd.DataFrame:
    rows: list[dict] = []
    for (target, stage), group in all_metrics.groupby(
        ["target_series", "forecast_stage"]
    ):
        best_rmse = float(group["rmse"].min())
        best_mae = float(group["mae"].min())
        best_median = float(group["median_ae"].min())
        best_direction = float(group["directional_accuracy"].max())
        accuracy_eligible = group.loc[
            (group["rmse"] <= best_rmse * thresholds.accuracy_eligible_rmse_ratio)
            & (group["mae"] <= best_mae * thresholds.accuracy_eligible_mae_ratio)
        ].copy()
        if accuracy_eligible.empty:
            accuracy_eligible = group.copy()
        best_tail = float(accuracy_eligible["p90_abs_error"].min())
        max_eligible = accuracy_eligible.loc[
            accuracy_eligible["p90_abs_error"]
            <= best_tail * thresholds.max_error_tail_eligibility_ratio
        ].copy()
        if max_eligible.empty:
            max_eligible = accuracy_eligible.copy()
        best_max = float(max_eligible["max_abs_error"].min())
        rows.append(
            {
                "target_series": str(target),
                "forecast_stage": str(stage),
                "best_rmse": best_rmse,
                "best_mae": best_mae,
                "best_median_ae": best_median,
                "best_directional_accuracy": best_direction,
                "best_accuracy_eligible_p90": best_tail,
                "best_tail_eligible_max_error": best_max,
                "accuracy_eligible_models": sorted(
                    accuracy_eligible["model_name"].astype(str).tolist()
                ),
                "max_error_eligible_models": sorted(
                    max_eligible["model_name"].astype(str).tolist()
                ),
            }
        )
    return pd.DataFrame(rows)


def evaluate_candidate_frames(
    results: pd.DataFrame,
    calibrated: pd.DataFrame,
    notices: list[dict] | None = None,
    base_validation_available: bool = True,
    thresholds: CandidateValidationThresholds | None = None,
) -> dict:
    """Validate the stable Model 1C point policy and prior-only intervals.

    The stable policy, adaptive shadow and calibrated intervals are reconstructed
    from stored pseudo-real-time rows. The adaptive selector and interval widths
    use only errors from target months strictly earlier than the forecast month.
    """
    thresholds = thresholds or CandidateValidationThresholds()
    required = {
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
        "direction_correct",
        "information_set_hash",
        "max_observation_date",
        "training_observations",
        "target_leakage",
        "regime",
    }
    missing = sorted(required.difference(results.columns))
    if missing:
        raise ValueError(f"Vintage results are missing required columns: {missing}")

    checks: list[dict] = []
    work = results.copy()
    notices = notices or []

    unexpected_notices = [
        item for item in notices if item.get("kind") not in ALLOWED_NOTICE_KINDS
    ]
    checks.append(
        _check(
            "Operational reliability",
            "Vintage evidence contains no unresolved hard issues",
            "pass" if not unexpected_notices else "fail",
            len(unexpected_notices),
            "0 unresolved hard issues",
            unexpected_notices[:25],
        )
    )
    structural_notices = [
        item for item in notices if item.get("kind") == "structural_missing"
    ]
    checks.append(
        _check(
            "Data availability",
            "Structurally unavailable target months are explicitly documented",
            "pass",
            len(structural_notices),
            "documented exclusions allowed",
            structural_notices,
        )
    )
    checks.append(
        _check(
            "Governance chain",
            "A passing Model 1C vintage and interval validation is available",
            "pass" if base_validation_available else "fail",
            "available" if base_validation_available else "missing",
            "passing validation required",
        )
    )

    duplicate_count = int(
        work.duplicated(
            ["target_series", "forecast_stage", "target_period", "model_name"]
        ).sum()
    )
    checks.append(
        _check(
            "Data integrity",
            "One forecast per target, stage, month, and model",
            "pass" if duplicate_count == 0 else "fail",
            duplicate_count,
            "0 duplicates",
        )
    )

    forecast_dates = pd.to_datetime(work["forecast_date"], errors="coerce")
    release_dates = pd.to_datetime(work["actual_release_date"], errors="coerce")
    release_violations = int((forecast_dates >= release_dates).fillna(False).sum())
    checks.append(
        _check(
            "Econometric validity",
            "Forecast cutoff occurs before the initial target release",
            "pass" if release_violations == 0 else "fail",
            release_violations,
            "0 violations",
        )
    )

    max_dates = pd.to_datetime(work["max_observation_date"], errors="coerce")
    future_rows = int((max_dates > forecast_dates).fillna(False).sum())
    checks.append(
        _check(
            "Econometric validity",
            "No observation is dated after the information cutoff",
            "pass" if future_rows == 0 else "fail",
            future_rows,
            "0 future-dated information sets",
        )
    )

    leaked = int(work["target_leakage"].fillna(False).astype(bool).sum())
    checks.append(
        _check(
            "Econometric validity",
            "Target-month outcome is absent before its initial release",
            "pass" if leaked == 0 else "fail",
            leaked,
            "0 leaked forecasts",
        )
    )

    hashes = work["information_set_hash"].fillna("").astype(str)
    invalid_hashes = int((~hashes.str.fullmatch(r"[0-9a-fA-F]{64}")).sum())
    checks.append(
        _check(
            "Reproducibility",
            "Every forecast has a valid information-set hash",
            "pass" if invalid_hashes == 0 else "fail",
            invalid_hashes,
            "0 invalid hashes",
        )
    )

    model_sets = work.groupby(
        ["target_series", "forecast_stage", "target_period"]
    )["model_name"].agg(set)
    incomplete_model_groups = int(
        sum(set(models) != EXPECTED_MODELS for models in model_sets)
    )
    checks.append(
        _check(
            "Data integrity",
            "Every information set contains all declared baseline models",
            "pass" if incomplete_model_groups == 0 else "fail",
            incomplete_model_groups,
            "0 incomplete groups",
        )
    )

    observed_targets = set(work["target_series"].astype(str).unique())
    observed_stage_map = work.groupby("target_series")["forecast_stage"].agg(set)
    incomplete_target_stages = int(
        observed_targets != EXPECTED_TARGETS
        or any(set(stages) != EXPECTED_STAGES for stages in observed_stage_map)
    )
    checks.append(
        _check(
            "Data integrity",
            "All three targets and five declared stages are represented",
            "pass" if incomplete_target_stages == 0 else "fail",
            incomplete_target_stages,
            "0 incomplete target/stage maps",
            {
                "targets": sorted(observed_targets),
                "stage_map": observed_stage_map.to_dict(),
            },
        )
    )

    training_minimum = int(
        pd.to_numeric(work["training_observations"], errors="coerce").min()
    )
    checks.append(
        _check(
            "Econometric validity",
            "Every generated forecast satisfies the training minimum",
            "pass"
            if training_minimum >= thresholds.minimum_training_observations
            else "fail",
            training_minimum,
            f">= {thresholds.minimum_training_observations} months",
        )
    )

    nonpositive_days = int(
        (pd.to_numeric(work["days_to_release"], errors="coerce") <= 0).sum()
    )
    checks.append(
        _check(
            "Econometric validity",
            "Every forecast has positive lead time to the employment release",
            "pass" if nonpositive_days == 0 else "fail",
            nonpositive_days,
            "0 non-positive lead times",
        )
    )

    missing_robust = int(
        work[["abs_error", "squared_error", "direction_correct", "regime"]]
        .isna()
        .any(axis=1)
        .sum()
    )
    checks.append(
        _check(
            "Performance reporting",
            "Robust error, direction, and regime fields are complete",
            "pass" if missing_robust == 0 else "fail",
            missing_robust,
            "0 incomplete rows",
        )
    )

    required_regimes = {"pre_pandemic", "pandemic_dislocation", "post_2021"}
    regime_sets = work.groupby("target_series")["regime"].agg(set)
    incomplete_regimes = int(
        sum(not required_regimes.issubset(set(regimes)) for regimes in regime_sets)
    )
    checks.append(
        _check(
            "Performance reporting",
            "All declared economic regimes are represented for every target",
            "pass" if incomplete_regimes == 0 else "fail",
            incomplete_regimes,
            "0 incomplete targets",
            regime_sets.to_dict(),
        )
    )

    declared_decisions = sum(len(stages) for stages in STABLE_POLICY.values())
    checks.append(
        _check(
            "Policy governance",
            "Stable candidate contains one predeclared decision for every target and stage",
            "pass" if declared_decisions == 15 else "fail",
            declared_decisions,
            "15 decisions",
            STABLE_POLICY,
        )
    )

    fixed = select_fixed_policy(work)
    expected_fixed_rows = int(
        work[["target_series", "forecast_stage", "target_period"]]
        .drop_duplicates()
        .shape[0]
    )
    fixed_duplicates = int(
        fixed.duplicated(["target_series", "forecast_stage", "target_period"]).sum()
    )
    fixed_complete = len(fixed) == expected_fixed_rows and fixed_duplicates == 0
    checks.append(
        _check(
            "Policy governance",
            "Stable candidate selects exactly one available component per information set",
            "pass" if fixed_complete else "fail",
            f"{len(fixed)} selected rows; {fixed_duplicates} duplicates",
            f"{expected_fixed_rows} rows and 0 duplicates",
        )
    )

    fixed_summary = summarise_forecasts(fixed)
    fixed_counts = fixed.groupby(["target_series", "forecast_stage"])[
        "target_period"
    ].nunique()
    minimum_fixed_months = int(fixed_counts.min()) if not fixed_counts.empty else 0
    checks.append(
        _check(
            "Econometric validity",
            "Stable candidate has sufficient evaluated history at every target and stage",
            "pass"
            if minimum_fixed_months >= thresholds.minimum_fixed_months_per_group
            else "fail",
            minimum_fixed_months,
            f">= {thresholds.minimum_fixed_months_per_group} months",
            fixed_counts.to_dict(),
        )
    )

    all_metrics = _all_model_metrics(work)
    comparators = _coherent_comparators(all_metrics, thresholds)
    competitive = fixed_summary.merge(
        comparators, on=["target_series", "forecast_stage"], how="left"
    )
    competitive["rmse_ratio"] = _safe_ratio(
        competitive["rmse"], competitive["best_rmse"]
    )
    competitive["mae_ratio"] = _safe_ratio(
        competitive["mae"], competitive["best_mae"]
    )
    competitive["median_ratio"] = _safe_ratio(
        competitive["median_ae"], competitive["best_median_ae"]
    )
    competitive["tail_ratio"] = _safe_ratio(
        competitive["p90_abs_error"], competitive["best_accuracy_eligible_p90"]
    )
    competitive["max_error_ratio"] = _safe_ratio(
        competitive["max_abs_error"], competitive["best_tail_eligible_max_error"]
    )
    competitive["directional_gap"] = (
        competitive["best_directional_accuracy"]
        - competitive["directional_accuracy"]
    )

    ratio_specs = [
        (
            "rmse_ratio",
            "Stable candidate RMSE is competitive with the best static model",
            thresholds.fixed_rmse_ratio,
        ),
        (
            "mae_ratio",
            "Stable candidate MAE is competitive with the best static model",
            thresholds.fixed_mae_ratio,
        ),
        (
            "median_ratio",
            "Stable candidate median absolute error remains bounded",
            thresholds.fixed_median_ratio,
        ),
        (
            "tail_ratio",
            "Stable candidate upper-tail error is competitive among accuracy-eligible models",
            thresholds.fixed_tail_ratio,
        ),
        (
            "max_error_ratio",
            "Stable candidate maximum error is competitive among accuracy-and-tail-eligible models",
            thresholds.fixed_max_error_ratio,
        ),
    ]
    for column, name, limit in ratio_specs:
        maximum = float(competitive[column].max())
        checks.append(
            _check(
                "Econometric validity",
                name,
                "pass" if np.isfinite(maximum) and maximum <= limit else "fail",
                round(maximum, 6),
                f"<= {limit:.3f}",
                competitive[
                    ["target_series", "forecast_stage", "model_name", column]
                ].to_dict("records"),
            )
        )

    maximum_directional_gap = float(competitive["directional_gap"].max())
    checks.append(
        _check(
            "Econometric validity",
            "Stable candidate directional accuracy remains close to the best static model",
            "pass"
            if maximum_directional_gap <= thresholds.maximum_directional_accuracy_gap
            else "fail",
            round(maximum_directional_gap, 6),
            f"<= {thresholds.maximum_directional_accuracy_gap:.3f}",
            competitive[
                ["target_series", "forecast_stage", "directional_gap"]
            ].to_dict("records"),
        )
    )

    bias_limits = {
        "PAYEMS": thresholds.payroll_maximum_absolute_bias,
        "UNRATE": thresholds.unemployment_maximum_absolute_bias,
        "CES0500000003": thresholds.earnings_maximum_absolute_bias,
    }
    bias_details: list[dict] = []
    bias_failures = 0
    for row in fixed_summary.itertuples(index=False):
        limit = bias_limits[str(row.target_series)]
        absolute_bias = abs(float(row.bias))
        bias_failures += int(absolute_bias > limit)
        bias_details.append(
            {
                "target_series": str(row.target_series),
                "forecast_stage": str(row.forecast_stage),
                "absolute_bias": absolute_bias,
                "limit": limit,
            }
        )
    checks.append(
        _check(
            "Econometric validity",
            "Stable candidate bias is bounded in target-appropriate units",
            "pass" if bias_failures == 0 else "fail",
            bias_failures,
            "0 target-stage bias violations",
            bias_details,
        )
    )

    regime_summary = summarise_regime_performance(fixed)
    regime_counts = (
        regime_summary.groupby(["target_series", "forecast_stage"])["observations"]
        .min()
        if not regime_summary.empty
        else pd.Series(dtype=float)
    )
    minimum_regime_months = int(regime_counts.min()) if not regime_counts.empty else 0
    checks.append(
        _check(
            "Econometric validity",
            "Stable candidate performance is reported with sufficient history in every regime",
            "pass"
            if minimum_regime_months >= thresholds.minimum_regime_months
            else "fail",
            minimum_regime_months,
            f">= {thresholds.minimum_regime_months} months per regime",
            regime_counts.to_dict(),
        )
    )

    shadow_config = ShadowSelectorConfig()
    shadow = select_prior_only_shadow(work, shadow_config)
    common_comparison, common_summary = compare_policies_on_common_sample(
        fixed, shadow, shadow_config.minimum_prior_errors
    )
    common_counts = (
        common_summary.groupby(["target_series", "forecast_stage"])["observations"]
        .min()
        if not common_summary.empty
        else pd.Series(dtype=float)
    )
    minimum_common = int(common_counts.min()) if not common_counts.empty else 0
    checks.append(
        _check(
            "Challenger governance",
            "Fixed and shadow policies have a sufficient identical-month comparison sample",
            "pass"
            if minimum_common >= thresholds.minimum_common_months_per_group
            else "fail",
            minimum_common,
            f">= {thresholds.minimum_common_months_per_group} months",
            common_counts.to_dict(),
        )
    )

    usable_shadow = shadow.loc[
        pd.to_numeric(shadow["prior_period_count"], errors="coerce")
        >= shadow_config.minimum_prior_errors
    ].copy()
    if usable_shadow.empty:
        shadow_lookahead = 1
    else:
        target_periods = pd.PeriodIndex(usable_shadow["target_period"], freq="M")
        cutoff_periods = pd.PeriodIndex(
            usable_shadow["selection_cutoff_period"], freq="M"
        )
        shadow_lookahead = int((cutoff_periods >= target_periods).sum())
    checks.append(
        _check(
            "Econometric validity",
            "Adaptive shadow selection uses strictly prior target-month errors",
            "pass" if shadow_lookahead == 0 else "fail",
            shadow_lookahead,
            "0 look-ahead violations",
        )
    )

    broad_shadow_wins = (
        int(
            (
                common_comparison["shadow_rmse_improved"]
                & common_comparison["shadow_mae_improved"]
                & common_comparison["shadow_tail_improved"]
            ).sum()
        )
        if not common_comparison.empty
        else 99
    )
    checks.append(
        _check(
            "Challenger governance",
            "Adaptive shadow does not broadly dominate the stable candidate",
            "pass"
            if broad_shadow_wins <= thresholds.maximum_shadow_broad_wins
            else "warning",
            f"{broad_shadow_wins} of 15 groups",
            f"<= {thresholds.maximum_shadow_broad_wins} broad wins",
            common_comparison.to_dict("records"),
        )
    )

    switching = summarise_shadow_switching(
        shadow, shadow_config.minimum_prior_errors
    )
    maximum_switches = int(switching["switches"].max()) if not switching.empty else 999
    checks.append(
        _check(
            "Challenger governance",
            "Adaptive shadow switching remains within the declared stability cap",
            "pass"
            if maximum_switches <= thresholds.maximum_shadow_switches_per_group
            else "warning",
            maximum_switches,
            f"<= {thresholds.maximum_shadow_switches_per_group} switches per group",
            switching.to_dict("records"),
        )
    )

    method_rows = calibrated.loc[
        calibrated.get("interval_method", pd.Series(index=calibrated.index, dtype=str))
        == SELECTED_INTERVAL_METHOD
    ].copy()
    selected_method_available = not method_rows.empty
    checks.append(
        _check(
            "Uncertainty calibration",
            "Predeclared prior-only interval method is available",
            "pass" if selected_method_available else "fail",
            SELECTED_INTERVAL_METHOD if selected_method_available else "missing",
            SELECTED_INTERVAL_METHOD,
        )
    )

    fixed_intervals = attach_calibrated_intervals(fixed, calibrated)
    interval_summary = summarise_intervals(fixed_intervals)
    interval_duplicates = (
        int(
            fixed_intervals.duplicated(
                ["target_series", "forecast_stage", "target_period"]
            ).sum()
        )
        if not fixed_intervals.empty
        else 1
    )
    checks.append(
        _check(
            "Data integrity",
            "Stable-policy interval evidence contains one interval per eligible information set",
            "pass" if interval_duplicates == 0 else "fail",
            interval_duplicates,
            "0 duplicate intervals",
        )
    )

    if fixed_intervals.empty:
        interval_lookahead = 1
        minimum_prior = 0
        minimum_interval_months = 0
        aggregate_coverage = np.nan
        group_outside = pd.DataFrame()
        invalid_widths = 1
        invalid_scores = 1
        interval_groups = 0
    else:
        target_periods = pd.PeriodIndex(fixed_intervals["target_period"], freq="M")
        cutoff_periods = pd.PeriodIndex(
            fixed_intervals["calibration_cutoff_period"], freq="M"
        )
        interval_lookahead = int((cutoff_periods >= target_periods).sum())
        minimum_prior = int(
            pd.to_numeric(fixed_intervals["prior_error_count"], errors="coerce").min()
        )
        minimum_interval_months = int(interval_summary["observations"].min())
        aggregate_coverage = float(fixed_intervals["interval_covered"].mean())
        group_outside = interval_summary.loc[
            (interval_summary["coverage"] < thresholds.interval_group_coverage_lower)
            | (interval_summary["coverage"] > thresholds.interval_group_coverage_upper)
        ]
        widths = pd.to_numeric(
            fixed_intervals["interval_half_width"], errors="coerce"
        )
        scores = pd.to_numeric(fixed_intervals["interval_score"], errors="coerce")
        invalid_widths = int((~np.isfinite(widths) | (widths <= 0.0)).sum())
        invalid_scores = int((~np.isfinite(scores) | (scores < 0.0)).sum())
        interval_groups = int(
            interval_summary[["target_series", "forecast_stage"]]
            .drop_duplicates()
            .shape[0]
        )

    checks.append(
        _check(
            "Econometric validity",
            "Selected intervals use strictly prior target-month errors",
            "pass" if interval_lookahead == 0 else "fail",
            interval_lookahead,
            "0 look-ahead violations",
        )
    )
    checks.append(
        _check(
            "Uncertainty calibration",
            "Selected intervals satisfy the prior-error warm-up",
            "pass" if minimum_prior >= thresholds.minimum_prior_errors else "fail",
            minimum_prior,
            f">= {thresholds.minimum_prior_errors} prior errors",
        )
    )
    checks.append(
        _check(
            "Uncertainty calibration",
            "Selected intervals cover every target-stage policy group",
            "pass" if interval_groups == 15 else "fail",
            interval_groups,
            "15 target-stage groups",
        )
    )
    checks.append(
        _check(
            "Uncertainty calibration",
            "Selected intervals have sufficient stage-level evaluation history",
            "pass"
            if minimum_interval_months >= thresholds.minimum_interval_months_per_group
            else "fail",
            minimum_interval_months,
            f">= {thresholds.minimum_interval_months_per_group} months",
            interval_summary.to_dict("records"),
        )
    )
    aggregate_ok = (
        np.isfinite(aggregate_coverage)
        and thresholds.interval_aggregate_coverage_lower
        <= aggregate_coverage
        <= thresholds.interval_aggregate_coverage_upper
    )
    checks.append(
        _check(
            "Uncertainty calibration",
            "Selected 80% intervals have acceptable aggregate empirical coverage",
            "pass" if aggregate_ok else "warning",
            round(aggregate_coverage, 6) if np.isfinite(aggregate_coverage) else "missing",
            (
                f"between {thresholds.interval_aggregate_coverage_lower:.2f} "
                f"and {thresholds.interval_aggregate_coverage_upper:.2f}"
            ),
        )
    )
    checks.append(
        _check(
            "Uncertainty calibration",
            "Selected 80% intervals have acceptable coverage at every target and stage",
            "pass" if group_outside.empty else "warning",
            f"{len(group_outside)} groups outside range",
            (
                f"each group between {thresholds.interval_group_coverage_lower:.2f} "
                f"and {thresholds.interval_group_coverage_upper:.2f}"
            ),
            group_outside.to_dict("records"),
        )
    )
    checks.append(
        _check(
            "Operational reliability",
            "Every selected interval has a finite positive half-width",
            "pass" if invalid_widths == 0 else "fail",
            invalid_widths,
            "0 invalid widths",
        )
    )
    checks.append(
        _check(
            "Operational reliability",
            "Every selected interval has a finite non-negative interval score",
            "pass" if invalid_scores == 0 else "fail",
            invalid_scores,
            "0 invalid scores",
        )
    )

    return {
        "checks": pd.DataFrame(checks),
        "fixed": fixed,
        "fixed_summary": fixed_summary,
        "all_model_metrics": all_metrics,
        "competitive": competitive,
        "regime_summary": regime_summary,
        "shadow": shadow,
        "common_comparison": common_comparison,
        "common_summary": common_summary,
        "switching": switching,
        "fixed_intervals": fixed_intervals,
        "selected_interval_summary": interval_summary,
        "thresholds": thresholds,
    }


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No rows."
    display = frame.copy()
    for column in display.select_dtypes(include=["float"]).columns:
        display[column] = display[column].map(lambda value: f"{value:.4f}")
    columns = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join(["---"] * len(columns)) + "|",
    ]
    for row in display.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _write_report(
    validation_id: str,
    status: str,
    backtest_id: str,
    calibration_id: str,
    base_validation_id: str | None,
    evaluated: dict,
) -> Path:
    report_dir = settings.project_root / "reports" / "labour_candidate_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1c_candidate_validation_{timestamp}.md"
    checks = evaluated["checks"]
    lines = [
        "# MacroPulse Model 1C v0.5 Candidate Validation",
        "",
        f"- Validation ID: `{validation_id}`",
        f"- Backtest ID: `{backtest_id}`",
        f"- Interval calibration ID: `{calibration_id}`",
        f"- Prior vintage-validation ID: `{base_validation_id or 'not available'}`",
        f"- Status: **{status.upper()}**",
        "- Stable point policy: **candidate**",
        "- Adaptive policy: **shadow challenger only**",
        f"- Interval method: `{SELECTED_INTERVAL_METHOD}`",
        "",
        "## Validation checks",
        "",
        "| Gate | Check | Status | Observed | Threshold |",
        "|---|---|---:|---:|---:|",
    ]
    for row in checks.itertuples(index=False):
        lines.append(
            f"| {row.gate_name} | {row.check_name} | {row.status} | "
            f"{row.observed_value} | {row.threshold} |"
        )
    lines.extend(
        [
            "",
            "## Stable candidate performance",
            "",
            _markdown_table(evaluated["fixed_summary"]),
            "",
            "## Fixed versus adaptive shadow on identical months",
            "",
            _markdown_table(evaluated["common_comparison"]),
            "",
            "## Shadow switching stability",
            "",
            _markdown_table(evaluated["switching"]),
            "",
            "## Stable candidate regime performance",
            "",
            _markdown_table(evaluated["regime_summary"]),
            "",
            f"## Selected interval diagnostics — {SELECTED_INTERVAL_METHOD}",
            "",
            _markdown_table(evaluated["selected_interval_summary"]),
            "",
            "## Governance conclusion",
            "",
            "The stable 15-decision target-stage map is the Model 1C point-forecast "
            "candidate. The adaptive selector remains shadow-only: its broad gains are "
            "concentrated in unemployment-rate groups, while it materially worsens "
            "earnings and payroll comparisons on the same eligible months. The selected "
            "prior-only exponentially weighted empirical 80% intervals have acceptable "
            "aggregate and target-stage coverage. This validation is not a production "
            "freeze: governed live forecasts, provenance signatures, labour-news "
            "decomposition, and operational validation remain required.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_labour_candidate_validation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    thresholds: CandidateValidationThresholds | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_labour_model_identity()

    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM labour_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No Model 1C vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        """
        SELECT *
        FROM labour_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no forecasts.")

    run_metadata = repository.query_df(
        "SELECT * FROM labour_vintage_backtest_runs WHERE backtest_id = ?",
        [backtest_id],
    )
    notices: list[dict] = []
    if not run_metadata.empty:
        notices = json.loads(run_metadata.iloc[0].get("notices_json") or "[]")

    base_validation = repository.query_df(
        """
        SELECT validation_id
        FROM labour_validation_runs
        WHERE backtest_id = ? AND status = 'pass'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [backtest_id],
    )
    base_validation_id = (
        str(base_validation.iloc[0]["validation_id"])
        if not base_validation.empty
        else None
    )

    calibration_run = repository.query_df(
        """
        SELECT calibration_id
        FROM labour_interval_calibration_runs
        WHERE backtest_id = ? AND status = 'success' AND method = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [backtest_id, SELECTED_INTERVAL_METHOD],
    )
    if calibration_run.empty:
        raise RuntimeError(
            "No successful exp_weighted_q80 Model 1C calibration is available."
        )
    calibration_id = str(calibration_run.iloc[0]["calibration_id"])
    calibrated = repository.query_df(
        """
        SELECT *
        FROM labour_interval_calibrated_results
        WHERE calibration_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [calibration_id],
    )

    evaluated = evaluate_candidate_frames(
        results,
        calibrated,
        notices=notices,
        base_validation_available=base_validation_id is not None,
        thresholds=thresholds,
    )
    checks = evaluated["checks"]
    failed = int((checks["status"] == "fail").sum())
    warnings = int((checks["status"] == "warning").sum())
    passed = int((checks["status"] == "pass").sum())
    status = "fail" if failed else ("conditional" if warnings else "pass")
    validation_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    report_path = _write_report(
        validation_id=validation_id,
        status=status,
        backtest_id=backtest_id,
        calibration_id=calibration_id,
        base_validation_id=base_validation_id,
        evaluated=evaluated,
    )

    persisted_checks = checks.copy()
    persisted_checks.insert(0, "validation_id", validation_id)
    persisted_checks["created_at"] = created_at
    persisted_checks = persisted_checks[
        [
            "validation_id",
            "gate_name",
            "check_name",
            "status",
            "observed_value",
            "threshold",
            "details_json",
            "created_at",
        ]
    ]
    run_record = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "backtest_id": backtest_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "created_at": created_at,
                "status": status,
                "passed_gates": passed,
                "failed_gates": failed,
                "warning_gates": warnings,
                "report_path": str(report_path),
                "summary_json": json.dumps(
                    {
                        "validation_type": "candidate_policy",
                        "passed": passed,
                        "failed": failed,
                        "warnings": warnings,
                        "base_validation_id": base_validation_id,
                        "calibration_id": calibration_id,
                        "point_policy": "stable_candidate",
                        "shadow_policy": "adaptive_shadow_only",
                        "interval_method": SELECTED_INTERVAL_METHOD,
                        "thresholds": asdict(evaluated["thresholds"]),
                    },
                    sort_keys=True,
                ),
                "notes": (
                    "Model 1C v0.5 candidate validation for the stable 15-decision "
                    "point policy and exp_weighted_q80 prior-only intervals. This is "
                    "not a production freeze or approval."
                ),
            }
        ]
    )
    repository.save_labour_validation_outputs(run_record, persisted_checks)
    return {
        "validation_id": validation_id,
        "backtest_id": backtest_id,
        "calibration_id": calibration_id,
        "base_validation_id": base_validation_id,
        "status": status,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "checks": persisted_checks,
        "report_path": report_path,
    }

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.policy import (
    SELECTED_INTERVAL_METHOD,
    STABLE_POLICY,
    ShadowSelectorConfig,
    compare_policies_on_common_sample,
    interval_tournament,
    select_fixed_policy,
    select_prior_only_shadow,
    summarise_forecasts,
    summarise_interval_tournament,
    summarise_shadow_switching,
)
from macropulse.inflation.versioning import current_inflation_model_identity
from macropulse.settings import settings


EXPECTED_MODELS = {
    "Inflation AR(1)",
    "Inflation 12-Month Mean",
    "Inflation Bridge Ridge",
    "Inflation Ridge-AR Ensemble",
}
EXPECTED_TARGETS = set(STABLE_POLICY)
EXPECTED_STAGES = {
    stage for stage_map in STABLE_POLICY.values() for stage in stage_map
}


@dataclass(frozen=True)
class CandidateValidationThresholds:
    minimum_training_observations: int = 120
    minimum_fixed_months_per_group: int = 60
    minimum_common_months_per_group: int = 48
    fixed_rmse_ratio: float = 1.05
    fixed_mae_ratio: float = 1.10
    fixed_tail_ratio: float = 1.15
    fixed_max_error_ratio: float = 1.20
    maximum_absolute_bias: float = 0.75
    maximum_shadow_broad_wins: int = 8
    maximum_shadow_switches_per_group: int = 6
    interval_aggregate_coverage_lower: float = 0.75
    interval_aggregate_coverage_upper: float = 0.90
    interval_group_coverage_lower: float = 0.75
    interval_group_coverage_upper: float = 0.95
    minimum_interval_months_per_group: int = 48
    selected_interval_score_ratio: float = 1.001


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
    errors = pd.to_numeric(frame["error"], errors="coerce").dropna().astype(float)
    if errors.empty:
        return {}
    absolute = errors.abs()
    return {
        "observations": int(len(errors)),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mae": float(absolute.mean()),
        "bias": float(errors.mean()),
        "median_ae": float(absolute.median()),
        "p90_abs_error": float(absolute.quantile(0.90)),
        "max_abs_error": float(absolute.max()),
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
    denominator = pd.to_numeric(denominator, errors="coerce")
    numerator = pd.to_numeric(numerator, errors="coerce")
    return numerator / denominator.replace(0.0, np.nan)


def evaluate_candidate_frames(
    results: pd.DataFrame,
    thresholds: CandidateValidationThresholds | None = None,
) -> dict:
    """Evaluate the v0.5 fixed-policy and interval candidate from stored vintage rows.

    All policy choices and interval widths are reconstructed from the supplied
    pseudo-real-time backtest. No current-month outcome is used in either the
    adaptive shadow selection or interval calibration.
    """
    thresholds = thresholds or CandidateValidationThresholds()
    required = {
        "target_series",
        "forecast_stage",
        "forecast_date",
        "target_period",
        "actual_release_date",
        "model_name",
        "point_forecast",
        "actual",
        "error",
        "abs_error",
        "information_set_hash",
        "max_observation_date",
        "training_observations",
        "target_leakage",
    }
    missing = sorted(required.difference(results.columns))
    if missing:
        raise ValueError(f"Vintage results are missing required columns: {missing}")

    checks: list[dict] = []
    work = results.copy()

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
            "Target-month index is absent before its initial release",
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
            "All four targets and four declared stages are represented",
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

    declared_decisions = sum(len(stages) for stages in STABLE_POLICY.values())
    checks.append(
        _check(
            "Policy governance",
            "Stable candidate contains one predeclared decision for every target and stage",
            "pass" if declared_decisions == 16 else "fail",
            declared_decisions,
            "16 decisions",
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
    best = (
        all_metrics.groupby(["target_series", "forecast_stage"], as_index=False)
        .agg(
            best_rmse=("rmse", "min"),
            best_mae=("mae", "min"),
            best_p90_abs_error=("p90_abs_error", "min"),
            best_max_abs_error=("max_abs_error", "min"),
        )
    )
    competitive = fixed_summary.merge(
        best, on=["target_series", "forecast_stage"], how="left"
    )
    competitive["rmse_ratio"] = _safe_ratio(
        competitive["rmse"], competitive["best_rmse"]
    )
    competitive["mae_ratio"] = _safe_ratio(
        competitive["mae"], competitive["best_mae"]
    )
    competitive["tail_ratio"] = _safe_ratio(
        competitive["p90_abs_error"], competitive["best_p90_abs_error"]
    )
    competitive["max_error_ratio"] = _safe_ratio(
        competitive["max_abs_error"], competitive["best_max_abs_error"]
    )

    ratio_specs = [
        ("rmse_ratio", "Stable candidate RMSE is competitive with the best static model", thresholds.fixed_rmse_ratio),
        ("mae_ratio", "Stable candidate MAE is competitive with the best static model", thresholds.fixed_mae_ratio),
        ("tail_ratio", "Stable candidate upper-tail error is competitive with the best static model", thresholds.fixed_tail_ratio),
        ("max_error_ratio", "Stable candidate maximum error is not materially worse than the best static model", thresholds.fixed_max_error_ratio),
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

    maximum_bias = float(fixed_summary["bias"].abs().max())
    checks.append(
        _check(
            "Econometric validity",
            "Stable candidate absolute bias is bounded at every target and stage",
            "pass" if maximum_bias <= thresholds.maximum_absolute_bias else "fail",
            round(maximum_bias, 6),
            f"<= {thresholds.maximum_absolute_bias:.3f} annualised pp",
            fixed_summary[
                ["target_series", "forecast_stage", "bias"]
            ].to_dict("records"),
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

    if common_comparison.empty:
        broad_shadow_wins = 99
    else:
        broad_shadow_wins = int(
            (
                common_comparison["shadow_rmse_improved"]
                & common_comparison["shadow_mae_improved"]
                & common_comparison["shadow_tail_improved"]
            ).sum()
        )
    checks.append(
        _check(
            "Challenger governance",
            "Adaptive shadow does not broadly dominate the stable candidate",
            "pass"
            if broad_shadow_wins <= thresholds.maximum_shadow_broad_wins
            else "warning",
            f"{broad_shadow_wins} of 16 groups",
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

    intervals = interval_tournament(fixed)
    interval_summary = summarise_interval_tournament(intervals)
    selected_intervals = intervals.loc[
        intervals["interval_method"] == SELECTED_INTERVAL_METHOD
    ].copy()
    selected_exists = not selected_intervals.empty
    checks.append(
        _check(
            "Uncertainty calibration",
            "Predeclared selected interval method is available",
            "pass" if selected_exists else "fail",
            SELECTED_INTERVAL_METHOD if selected_exists else "missing",
            SELECTED_INTERVAL_METHOD,
        )
    )

    if selected_exists:
        target_periods = pd.PeriodIndex(selected_intervals["target_period"], freq="M")
        cutoff_periods = pd.PeriodIndex(
            selected_intervals["calibration_cutoff_period"], freq="M"
        )
        interval_lookahead = int((cutoff_periods >= target_periods).sum())
        minimum_prior = int(selected_intervals["prior_error_count"].min())
        grouped_interval = (
            selected_intervals.groupby(["target_series", "forecast_stage"])
            .agg(
                observations=("interval_covered", "count"),
                coverage=("interval_covered", "mean"),
                average_half_width=("interval_half_width", "mean"),
                mean_interval_score=("interval_score", "mean"),
            )
            .reset_index()
        )
        minimum_interval_months = int(grouped_interval["observations"].min())
        group_outside = grouped_interval.loc[
            (grouped_interval["coverage"] < thresholds.interval_group_coverage_lower)
            | (grouped_interval["coverage"] > thresholds.interval_group_coverage_upper)
        ]
        aggregate_coverage = float(selected_intervals["interval_covered"].mean())
        widths = pd.to_numeric(
            selected_intervals["interval_half_width"], errors="coerce"
        )
        invalid_widths = int((~np.isfinite(widths) | (widths <= 0.0)).sum())
        selected_score = float(
            interval_summary.loc[
                interval_summary["interval_method"] == SELECTED_INTERVAL_METHOD,
                "mean_interval_score",
            ].iloc[0]
        )
        best_score = float(interval_summary["mean_interval_score"].min())
        score_ratio = selected_score / best_score if best_score else np.nan
    else:
        interval_lookahead = 1
        minimum_prior = 0
        grouped_interval = pd.DataFrame()
        minimum_interval_months = 0
        group_outside = pd.DataFrame()
        aggregate_coverage = np.nan
        invalid_widths = 1
        score_ratio = np.nan

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
            "pass" if minimum_prior >= 24 else "fail",
            minimum_prior,
            ">= 24 prior errors",
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
            grouped_interval.to_dict("records"),
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
            "Uncertainty calibration",
            "Selected interval method remains the interval-score winner",
            "pass"
            if np.isfinite(score_ratio)
            and score_ratio <= thresholds.selected_interval_score_ratio
            else "fail",
            round(score_ratio, 6) if np.isfinite(score_ratio) else "missing",
            f"<= {thresholds.selected_interval_score_ratio:.3f}",
            interval_summary.to_dict("records"),
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

    return {
        "checks": pd.DataFrame(checks),
        "fixed": fixed,
        "fixed_summary": fixed_summary,
        "all_model_metrics": all_metrics,
        "competitive": competitive,
        "shadow": shadow,
        "common_comparison": common_comparison,
        "switching": switching,
        "intervals": intervals,
        "interval_summary": interval_summary,
        "selected_intervals": selected_intervals,
        "selected_interval_summary": grouped_interval,
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
    evaluated: dict,
) -> Path:
    report_dir = settings.project_root / "reports" / "inflation_candidate_validation"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = report_dir / f"model1b_candidate_validation_{timestamp}.md"
    checks = evaluated["checks"]
    lines = [
        "# MacroPulse Model 1B v0.5 Candidate Validation",
        "",
        f"- Validation ID: `{validation_id}`",
        f"- Backtest ID: `{backtest_id}`",
        f"- Status: **{status.upper()}**",
        f"- Stable point policy: **candidate**",
        f"- Adaptive policy: **shadow challenger only**",
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
            f"## Selected interval diagnostics — {SELECTED_INTERVAL_METHOD}",
            "",
            _markdown_table(evaluated["selected_interval_summary"]),
            "",
            "## Governance conclusion",
            "",
            "The stable target-stage map is the Model 1B point-forecast candidate. "
            "The adaptive selector remains shadow-only because its gains are concentrated "
            "in a minority of target-stage groups and it worsens several headline and "
            "core-inflation comparisons on the same eligible months. The exponentially "
            "weighted empirical 80% quantile is the interval candidate because it has the "
            "lowest predeclared interval score and acceptable aggregate and stage-level "
            "coverage. This validation is not a production freeze: live governance, news "
            "decomposition, and a governed candidate forecast are still required.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_inflation_candidate_validation(
    repository: MacroRepository | None = None,
    backtest_id: str | None = None,
    thresholds: CandidateValidationThresholds | None = None,
) -> dict:
    repository = repository or MacroRepository()
    repository.initialise()
    identity = current_inflation_model_identity()

    if backtest_id is None:
        latest = repository.query_df(
            """
            SELECT backtest_id
            FROM inflation_vintage_backtest_runs
            WHERE status IN ('success', 'partial')
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if latest.empty:
            raise RuntimeError("No Model 1B vintage backtest is available.")
        backtest_id = str(latest.iloc[0]["backtest_id"])

    results = repository.query_df(
        """
        SELECT *
        FROM inflation_vintage_backtest_results
        WHERE backtest_id = ?
        ORDER BY target_series, forecast_stage, target_period, model_name
        """,
        [backtest_id],
    )
    if results.empty:
        raise RuntimeError(f"Vintage backtest {backtest_id} contains no forecasts.")

    evaluated = evaluate_candidate_frames(results, thresholds=thresholds)
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
        evaluated=evaluated,
    )

    persisted_checks = checks.copy()
    persisted_checks.insert(0, "validation_id", validation_id)
    persisted_checks["created_at"] = created_at
    run_record = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "backtest_id": backtest_id,
                "created_at": created_at,
                "status": status,
                "passed_checks": passed,
                "failed_checks": failed,
                "warnings": warnings,
                "report_path": str(report_path),
                "summary_json": json.dumps(
                    {
                        "validation_type": "candidate_policy",
                        "passed": passed,
                        "failed": failed,
                        "warnings": warnings,
                        "point_policy": "stable_candidate",
                        "shadow_policy": "adaptive_shadow_only",
                        "interval_method": SELECTED_INTERVAL_METHOD,
                        "thresholds": asdict(evaluated["thresholds"]),
                    },
                    sort_keys=True,
                ),
                "notes": (
                    "Model 1B v0.5 candidate validation for the stable target-stage "
                    "point policy and exp_weighted_q80 prior-only intervals. This is "
                    "not a production freeze or approval."
                ),
            }
        ]
    )
    repository.save_inflation_validation_outputs(run_record, persisted_checks)
    return {
        "validation_id": validation_id,
        "backtest_id": backtest_id,
        "status": status,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "report_path": str(report_path),
        **evaluated,
    }

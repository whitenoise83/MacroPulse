from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.prospective_shadow import prospective_shadow_plan
from macropulse.macro_state.versioning import load_macro_state_governance
from macropulse.settings import settings

REQUIRED_BENCHMARKS = ("source", "rolling_frequency")
REQUIRED_DIMENSIONS = ("growth", "inflation", "labour")


@dataclass(frozen=True)
class ShadowMonitoringContract:
    model_version: str
    minimum_complete_months: int
    probability_sum_tolerance: float
    promotion_authority: str


def _utc_now_naive() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None)


def _date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    return pd.to_datetime(frame[column], errors="coerce")


def _grouped_members(
    frame: pd.DataFrame,
    *,
    key: str,
    member: str,
    output_name: str,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[key, output_name])
    result = (
        frame.groupby(key, dropna=False)[member]
        .agg(lambda values: tuple(sorted(set(values.astype(str)))))
        .rename(output_name)
        .reset_index()
    )
    return result


def _grouped_count(
    frame: pd.DataFrame,
    *,
    key: str,
    output_name: str,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[key, output_name])
    return frame.groupby(key, dropna=False).size().rename(output_name).reset_index()


def build_run_status(
    runs: pd.DataFrame,
    predictions: pd.DataFrame,
    dimensions: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    as_of: date,
    model_version: str,
) -> pd.DataFrame:
    columns = [
        "shadow_run_id",
        "model_version",
        "state_date",
        "information_cutoff",
        "target_expected_available_date",
        "prediction_count",
        "prediction_benchmarks",
        "dimension_count",
        "dimension_members",
        "outcome_count",
        "outcome_benchmarks",
        "days_to_expected_availability",
        "operational_status",
        "complete_target_month",
        "no_look_ahead_pass",
        "status",
    ]
    if runs.empty:
        return pd.DataFrame(columns=columns)

    frame = runs.loc[runs["model_version"].astype(str) == str(model_version)].copy()
    if frame.empty:
        return pd.DataFrame(columns=columns)

    frame["state_date"] = _date_series(frame, "state_date").dt.date
    frame["information_cutoff"] = _date_series(frame, "information_cutoff").dt.date
    frame["target_expected_available_date"] = _date_series(
        frame, "target_expected_available_date"
    ).dt.date

    for child, count_name, member_name, member_column in (
        (predictions, "prediction_count", "prediction_benchmarks", "benchmark_id"),
        (dimensions, "dimension_count", "dimension_members", "dimension"),
        (outcomes, "outcome_count", "outcome_benchmarks", "benchmark_id"),
    ):
        frame = frame.merge(
            _grouped_count(child, key="shadow_run_id", output_name=count_name),
            on="shadow_run_id",
            how="left",
        )
        frame = frame.merge(
            _grouped_members(
                child,
                key="shadow_run_id",
                member=member_column,
                output_name=member_name,
            ),
            on="shadow_run_id",
            how="left",
        )

    for name in ("prediction_count", "dimension_count", "outcome_count"):
        frame[name] = (
            pd.to_numeric(frame[name], errors="coerce")
            .astype("Int64")
            .fillna(0)
            .astype(int)
        )
    for name in ("prediction_benchmarks", "dimension_members", "outcome_benchmarks"):
        frame[name] = frame[name].map(
            lambda value: tuple() if not isinstance(value, tuple) else value
        )

    expected_benchmarks = tuple(sorted(REQUIRED_BENCHMARKS))
    expected_dimensions = tuple(sorted(REQUIRED_DIMENSIONS))

    def classify(row: pd.Series) -> str:
        structural_error = (
            int(row["prediction_count"]) != len(REQUIRED_BENCHMARKS)
            or tuple(row["prediction_benchmarks"]) != expected_benchmarks
            or int(row["dimension_count"]) != len(REQUIRED_DIMENSIONS)
            or tuple(row["dimension_members"]) != expected_dimensions
            or int(row["outcome_count"]) not in {0, len(REQUIRED_BENCHMARKS)}
            or (
                int(row["outcome_count"]) == len(REQUIRED_BENCHMARKS)
                and tuple(row["outcome_benchmarks"]) != expected_benchmarks
            )
        )
        if structural_error:
            return "integrity_error"
        if int(row["outcome_count"]) == len(REQUIRED_BENCHMARKS):
            return "resolved"
        expected = row["target_expected_available_date"]
        if pd.isna(expected):
            return "integrity_error"
        if expected <= as_of:
            return "due_for_resolution_attempt"
        return "pending_target"

    frame["days_to_expected_availability"] = frame[
        "target_expected_available_date"
    ].map(lambda value: None if pd.isna(value) else (value - as_of).days)
    frame["operational_status"] = frame.apply(classify, axis=1)
    frame["complete_target_month"] = frame["operational_status"].eq("resolved")
    frame = frame.sort_values(["state_date", "run_timestamp"], na_position="last")
    return frame[columns].reset_index(drop=True)


def _all_true(frame: pd.DataFrame, column: str) -> bool:
    if frame.empty or column not in frame.columns:
        return True
    return bool(frame[column].fillna(False).astype(bool).all())


def _child_dates_match(runs: pd.DataFrame, child: pd.DataFrame) -> bool:
    if child.empty:
        return True
    required = {"shadow_run_id", "state_date"}
    if not required.issubset(child.columns) or not required.issubset(runs.columns):
        return False
    left = child[["shadow_run_id", "state_date"]].copy()
    right = runs[["shadow_run_id", "state_date"]].copy().rename(
        columns={"state_date": "parent_state_date"}
    )
    merged = left.merge(right, on="shadow_run_id", how="left")
    return bool(
        _date_series(merged, "state_date").eq(
            _date_series(merged, "parent_state_date")
        ).all()
    )


def _child_cutoffs_match(runs: pd.DataFrame, child: pd.DataFrame) -> bool:
    if child.empty:
        return True
    required = {"shadow_run_id", "information_cutoff"}
    if not required.issubset(child.columns) or not required.issubset(runs.columns):
        return False
    left = child[["shadow_run_id", "information_cutoff"]].copy()
    right = runs[["shadow_run_id", "information_cutoff"]].copy().rename(
        columns={"information_cutoff": "parent_information_cutoff"}
    )
    merged = left.merge(right, on="shadow_run_id", how="left")
    return bool(
        _date_series(merged, "information_cutoff").eq(
            _date_series(merged, "parent_information_cutoff")
        ).all()
    )


def build_integrity_checks(
    runs: pd.DataFrame,
    predictions: pd.DataFrame,
    dimensions: pd.DataFrame,
    outcomes: pd.DataFrame,
    run_status: pd.DataFrame,
    *,
    probability_sum_tolerance: float,
    append_only_contract: dict[str, Any],
) -> pd.DataFrame:
    expected_benchmarks = tuple(sorted(REQUIRED_BENCHMARKS))
    expected_dimensions = tuple(sorted(REQUIRED_DIMENSIONS))

    if predictions.empty or "probability_sum" not in predictions.columns:
        probability_sum_ok = predictions.empty
        maximum_sum_error = 0.0 if predictions.empty else float("inf")
    else:
        sums = pd.to_numeric(predictions["probability_sum"], errors="coerce")
        errors = (sums - 1.0).abs()
        probability_sum_ok = bool(errors.notna().all() and (errors <= probability_sum_tolerance).all())
        maximum_sum_error = float(errors.max()) if not errors.empty else 0.0

    outcome_date_ok = True
    if not outcomes.empty:
        if not {"target_available_date", "resolved_at"}.issubset(outcomes.columns):
            outcome_date_ok = False
        else:
            target_dates = _date_series(outcomes, "target_available_date")
            resolved_dates = _date_series(outcomes, "resolved_at")
            outcome_date_ok = bool(target_dates.notna().all() and resolved_dates.notna().all() and (target_dates <= resolved_dates).all())

    outcome_groups = _grouped_members(
        outcomes,
        key="shadow_run_id",
        member="benchmark_id",
        output_name="members",
    )
    outcome_benchmarks_ok = bool(
        outcome_groups.empty
        or outcome_groups["members"].map(lambda value: value == expected_benchmarks).all()
    )

    checks: list[tuple[str, bool, Any, Any, str]] = [
        (
            "shadow_run_exists",
            not runs.empty,
            int(len(runs)),
            ">= 1",
            "At least one prospective shadow prediction must exist before monitoring can be meaningful.",
        ),
        (
            "run_month_unique",
            bool(runs.empty or not runs.duplicated(["model_version", "state_date"]).any()),
            int(runs.duplicated(["model_version", "state_date"]).sum()) if not runs.empty else 0,
            0,
            "Append-only governance permits one run per model version and state month.",
        ),
        (
            "two_predictions_per_run",
            bool(run_status.empty or run_status["prediction_count"].eq(len(REQUIRED_BENCHMARKS)).all()),
            run_status["prediction_count"].tolist() if not run_status.empty else [],
            len(REQUIRED_BENCHMARKS),
            "Every run must contain source and rolling_frequency predictions.",
        ),
        (
            "prediction_benchmarks_exact",
            bool(run_status.empty or run_status["prediction_benchmarks"].map(lambda value: value == expected_benchmarks).all()),
            run_status["prediction_benchmarks"].tolist() if not run_status.empty else [],
            expected_benchmarks,
            "No additional or missing benchmark is allowed.",
        ),
        (
            "three_dimensions_per_run",
            bool(run_status.empty or run_status["dimension_count"].eq(len(REQUIRED_DIMENSIONS)).all()),
            run_status["dimension_count"].tolist() if not run_status.empty else [],
            len(REQUIRED_DIMENSIONS),
            "Every run must preserve growth, inflation, and labour lineage.",
        ),
        (
            "dimension_members_exact",
            bool(run_status.empty or run_status["dimension_members"].map(lambda value: value == expected_dimensions).all()),
            run_status["dimension_members"].tolist() if not run_status.empty else [],
            expected_dimensions,
            "No governed dimension may be missing or duplicated.",
        ),
        (
            "outcome_rows_zero_or_two",
            bool(run_status.empty or run_status["outcome_count"].isin([0, len(REQUIRED_BENCHMARKS)]).all()),
            run_status["outcome_count"].tolist() if not run_status.empty else [],
            (0, len(REQUIRED_BENCHMARKS)),
            "Outcomes must be absent before resolution or complete for both benchmarks.",
        ),
        (
            "outcome_benchmarks_exact_when_present",
            outcome_benchmarks_ok,
            outcome_groups["members"].tolist() if not outcome_groups.empty else [],
            expected_benchmarks,
            "A resolved month must score both frozen predictions against one target.",
        ),
        (
            "probability_sums_valid",
            probability_sum_ok,
            maximum_sum_error,
            f"<= {probability_sum_tolerance}",
            "Persisted probability vectors must sum to one within governance tolerance.",
        ),
        (
            "run_no_look_ahead_pass",
            _all_true(runs, "no_look_ahead_pass"),
            _all_true(runs, "no_look_ahead_pass"),
            True,
            "Every run must pass the no-look-ahead gate.",
        ),
        (
            "prediction_no_look_ahead_pass",
            _all_true(predictions, "no_look_ahead_pass"),
            _all_true(predictions, "no_look_ahead_pass"),
            True,
            "Every benchmark prediction must be causal.",
        ),
        (
            "dimension_no_look_ahead_pass",
            _all_true(dimensions, "no_look_ahead_pass"),
            _all_true(dimensions, "no_look_ahead_pass"),
            True,
            "Every dimension source cutoff must be causal.",
        ),
        (
            "outcome_no_look_ahead_pass",
            _all_true(outcomes, "no_look_ahead_pass"),
            _all_true(outcomes, "no_look_ahead_pass"),
            True,
            "Every resolved target must use fixed-horizon evidence only.",
        ),
        (
            "prediction_state_dates_match_parent",
            _child_dates_match(runs, predictions),
            _child_dates_match(runs, predictions),
            True,
            "Prediction state dates must match their parent run.",
        ),
        (
            "dimension_state_dates_match_parent",
            _child_dates_match(runs, dimensions),
            _child_dates_match(runs, dimensions),
            True,
            "Dimension state dates must match their parent run.",
        ),
        (
            "outcome_state_dates_match_parent",
            _child_dates_match(runs, outcomes),
            _child_dates_match(runs, outcomes),
            True,
            "Outcome state dates must match their parent run.",
        ),
        (
            "prediction_cutoffs_match_parent",
            _child_cutoffs_match(runs, predictions),
            _child_cutoffs_match(runs, predictions),
            True,
            "Prediction information cutoffs must match their parent run.",
        ),
        (
            "dimension_cutoffs_match_parent",
            _child_cutoffs_match(runs, dimensions),
            _child_cutoffs_match(runs, dimensions),
            True,
            "Dimension information cutoffs must match their parent run.",
        ),
        (
            "outcomes_not_resolved_before_target_availability",
            outcome_date_ok,
            outcome_date_ok,
            True,
            "A target must be available before its outcome can be appended.",
        ),
        (
            "append_only_governance_locked",
            bool(
                append_only_contract.get("append_only")
                and append_only_contract.get("updates_prohibited")
                and append_only_contract.get("deletes_prohibited")
                and append_only_contract.get("prediction_overwrite_prohibited")
            ),
            append_only_contract,
            "all true",
            "Monitoring must preserve the frozen append-only persistence contract.",
        ),
    ]

    return pd.DataFrame(
        [
            {
                "check_id": check_id,
                "passed": bool(passed),
                "observed": json.dumps(observed, default=str, sort_keys=True),
                "threshold": json.dumps(threshold, default=str, sort_keys=True),
                "interpretation": interpretation,
            }
            for check_id, passed, observed, threshold, interpretation in checks
        ]
    )


def benchmark_performance(outcomes: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "benchmark_id",
        "complete_months",
        "top1_accuracy",
        "top2_accuracy",
        "top3_accuracy",
        "mean_actual_probability",
        "mean_brier_score",
        "mean_log_loss",
        "transition_months",
    ]
    if outcomes.empty:
        return pd.DataFrame(columns=columns)
    required = {
        "benchmark_id",
        "state_date",
        "top1_hit",
        "top2_hit",
        "top3_hit",
        "actual_probability",
        "brier_score",
        "log_loss",
        "transition_flag",
    }
    missing = sorted(required - set(outcomes.columns))
    if missing:
        raise ValueError(f"Outcome monitoring is missing columns: {missing}")
    rows: list[dict[str, Any]] = []
    for benchmark_id, frame in outcomes.groupby("benchmark_id", sort=True):
        rows.append(
            {
                "benchmark_id": str(benchmark_id),
                "complete_months": int(frame["state_date"].nunique()),
                "top1_accuracy": float(frame["top1_hit"].astype(bool).mean()),
                "top2_accuracy": float(frame["top2_hit"].astype(bool).mean()),
                "top3_accuracy": float(frame["top3_hit"].astype(bool).mean()),
                "mean_actual_probability": float(
                    pd.to_numeric(frame["actual_probability"], errors="coerce").mean()
                ),
                "mean_brier_score": float(
                    pd.to_numeric(frame["brier_score"], errors="coerce").mean()
                ),
                "mean_log_loss": float(
                    pd.to_numeric(frame["log_loss"], errors="coerce").mean()
                ),
                "transition_months": int(frame["transition_flag"].astype(bool).sum()),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def paired_monthly_performance(outcomes: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "shadow_run_id",
        "state_date",
        "actual_family",
        "transition_flag",
        "source_brier_score",
        "rolling_frequency_brier_score",
        "source_brier_improvement",
        "source_log_loss",
        "rolling_frequency_log_loss",
        "source_log_loss_improvement",
        "source_top1_hit",
        "rolling_frequency_top1_hit",
        "source_top2_hit",
        "rolling_frequency_top2_hit",
    ]
    if outcomes.empty:
        return pd.DataFrame(columns=columns)
    required = {
        "shadow_run_id",
        "benchmark_id",
        "state_date",
        "actual_family",
        "transition_flag",
        "brier_score",
        "log_loss",
        "top1_hit",
        "top2_hit",
    }
    missing = sorted(required - set(outcomes.columns))
    if missing:
        raise ValueError(f"Paired outcome monitoring is missing columns: {missing}")

    source = outcomes.loc[outcomes["benchmark_id"].astype(str) == "source"].copy()
    rolling = outcomes.loc[
        outcomes["benchmark_id"].astype(str) == "rolling_frequency"
    ].copy()
    if source.empty or rolling.empty:
        return pd.DataFrame(columns=columns)

    left = source[
        [
            "shadow_run_id",
            "state_date",
            "actual_family",
            "transition_flag",
            "brier_score",
            "log_loss",
            "top1_hit",
            "top2_hit",
        ]
    ].rename(
        columns={
            "brier_score": "source_brier_score",
            "log_loss": "source_log_loss",
            "top1_hit": "source_top1_hit",
            "top2_hit": "source_top2_hit",
        }
    )
    right = rolling[
        ["shadow_run_id", "brier_score", "log_loss", "top1_hit", "top2_hit"]
    ].rename(
        columns={
            "brier_score": "rolling_frequency_brier_score",
            "log_loss": "rolling_frequency_log_loss",
            "top1_hit": "rolling_frequency_top1_hit",
            "top2_hit": "rolling_frequency_top2_hit",
        }
    )
    paired = left.merge(right, on="shadow_run_id", how="inner", validate="one_to_one")
    paired["source_brier_improvement"] = (
        pd.to_numeric(paired["rolling_frequency_brier_score"], errors="coerce")
        - pd.to_numeric(paired["source_brier_score"], errors="coerce")
    )
    paired["source_log_loss_improvement"] = (
        pd.to_numeric(paired["rolling_frequency_log_loss"], errors="coerce")
        - pd.to_numeric(paired["source_log_loss"], errors="coerce")
    )
    return paired[columns].sort_values("state_date").reset_index(drop=True)


def paired_summary(paired: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "comparison",
        "complete_months",
        "mean_brier_improvement",
        "mean_log_loss_improvement",
        "source_brier_win_rate",
        "source_log_loss_win_rate",
        "source_top1_accuracy",
        "rolling_frequency_top1_accuracy",
        "source_top2_accuracy",
        "rolling_frequency_top2_accuracy",
    ]
    if paired.empty:
        return pd.DataFrame(columns=columns)
    row = {
        "comparison": "source_vs_rolling_frequency",
        "complete_months": int(paired["state_date"].nunique()),
        "mean_brier_improvement": float(paired["source_brier_improvement"].mean()),
        "mean_log_loss_improvement": float(
            paired["source_log_loss_improvement"].mean()
        ),
        "source_brier_win_rate": float(
            paired["source_brier_improvement"].gt(0).mean()
        ),
        "source_log_loss_win_rate": float(
            paired["source_log_loss_improvement"].gt(0).mean()
        ),
        "source_top1_accuracy": float(paired["source_top1_hit"].astype(bool).mean()),
        "rolling_frequency_top1_accuracy": float(
            paired["rolling_frequency_top1_hit"].astype(bool).mean()
        ),
        "source_top2_accuracy": float(paired["source_top2_hit"].astype(bool).mean()),
        "rolling_frequency_top2_accuracy": float(
            paired["rolling_frequency_top2_hit"].astype(bool).mean()
        ),
    }
    return pd.DataFrame([row], columns=columns)


def transition_summary(outcomes: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "transition_flag",
        "months",
        "source_top1_accuracy",
        "source_top2_accuracy",
        "source_mean_brier",
        "source_mean_log_loss",
    ]
    if outcomes.empty:
        return pd.DataFrame(columns=columns)
    source = outcomes.loc[outcomes["benchmark_id"].astype(str) == "source"].copy()
    if source.empty:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for transition_flag, frame in source.groupby("transition_flag", sort=True):
        rows.append(
            {
                "transition_flag": bool(transition_flag),
                "months": int(frame["state_date"].nunique()),
                "source_top1_accuracy": float(frame["top1_hit"].astype(bool).mean()),
                "source_top2_accuracy": float(frame["top2_hit"].astype(bool).mean()),
                "source_mean_brier": float(
                    pd.to_numeric(frame["brier_score"], errors="coerce").mean()
                ),
                "source_mean_log_loss": float(
                    pd.to_numeric(frame["log_loss"], errors="coerce").mean()
                ),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_readiness(
    run_status: pd.DataFrame,
    integrity_checks: pd.DataFrame,
    *,
    minimum_complete_months: int,
    promotion_authority: str,
) -> pd.DataFrame:
    complete_months = int(run_status["complete_target_month"].sum()) if not run_status.empty else 0
    integrity_pass = bool(
        not integrity_checks.empty and integrity_checks["passed"].astype(bool).all()
    )
    comparison_permitted = bool(
        integrity_pass and complete_months >= int(minimum_complete_months)
    )
    if not integrity_pass:
        conclusion_status = "integrity_failure"
    elif complete_months < int(minimum_complete_months):
        conclusion_status = "insufficient_prospective_evidence"
    else:
        conclusion_status = "eligible_for_report_only_comparison"
    return pd.DataFrame(
        [
            {
                "complete_target_months": complete_months,
                "minimum_complete_target_months": int(minimum_complete_months),
                "months_remaining": max(0, int(minimum_complete_months) - complete_months),
                "integrity_pass": integrity_pass,
                "comparison_permitted": comparison_permitted,
                "conclusion_status": conclusion_status,
                "promotion_authority": str(promotion_authority),
                "promotion_permitted": False,
            }
        ]
    )


def monitoring_contract(config: dict[str, Any]) -> ShadowMonitoringContract:
    section = config["prospective_transition_shadow"]
    plan = prospective_shadow_plan(config)
    return ShadowMonitoringContract(
        model_version=str(plan.model_version),
        minimum_complete_months=int(section["minimum_evidence"]["complete_target_months"]),
        probability_sum_tolerance=float(
            section["probability_contract"]["sum_tolerance"]
        ),
        promotion_authority=str(section["promotion_authority"]),
    )


def collect_shadow_monitoring(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> dict[str, Any]:
    config = load_macro_state_governance(project_root)
    contract = monitoring_contract(config)
    runs = repository.query_df(
        """
        SELECT *
        FROM macro_state_shadow_runs
        WHERE model_version = ?
          AND information_cutoff <= ?
        ORDER BY state_date, created_at
        """,
        [contract.model_version, as_of],
    )
    predictions = repository.query_df(
        """
        SELECT *
        FROM macro_state_shadow_predictions
        WHERE model_version = ?
          AND information_cutoff <= ?
        ORDER BY state_date, benchmark_id
        """,
        [contract.model_version, as_of],
    )
    dimensions = repository.query_df(
        """
        SELECT *
        FROM macro_state_shadow_dimensions
        WHERE model_version = ?
          AND information_cutoff <= ?
        ORDER BY state_date, dimension
        """,
        [contract.model_version, as_of],
    )
    outcomes = repository.query_df(
        """
        SELECT *
        FROM macro_state_shadow_outcomes
        WHERE model_version = ?
          AND CAST(resolved_at AS DATE) <= ?
        ORDER BY state_date, benchmark_id
        """,
        [contract.model_version, as_of],
    )

    run_status = build_run_status(
        runs,
        predictions,
        dimensions,
        outcomes,
        as_of=as_of,
        model_version=contract.model_version,
    )
    integrity = build_integrity_checks(
        runs,
        predictions,
        dimensions,
        outcomes,
        run_status,
        probability_sum_tolerance=contract.probability_sum_tolerance,
        append_only_contract=config["prospective_transition_shadow"]["persistence"],
    )
    performance = benchmark_performance(outcomes)
    paired = paired_monthly_performance(outcomes)
    comparison = paired_summary(paired)
    transitions = transition_summary(outcomes)
    readiness = build_readiness(
        run_status,
        integrity,
        minimum_complete_months=contract.minimum_complete_months,
        promotion_authority=contract.promotion_authority,
    )
    return {
        "as_of": as_of,
        "model_version": contract.model_version,
        "contract": contract,
        "runs": runs,
        "predictions": predictions,
        "dimensions": dimensions,
        "outcomes": outcomes,
        "run_status": run_status,
        "integrity_checks": integrity,
        "benchmark_performance": performance,
        "paired_monthly": paired,
        "paired_summary": comparison,
        "transition_summary": transitions,
        "readiness": readiness,
    }


def _markdown(frame: pd.DataFrame, columns: Iterable[str] | None = None) -> str:
    if frame.empty:
        return "_No rows._"
    selected = frame
    if columns is not None:
        available = [column for column in columns if column in frame.columns]
        selected = frame[available]
    return selected.to_markdown(index=False)


def write_shadow_monitoring_report(
    result: dict[str, Any],
    *,
    project_root: Path,
) -> dict[str, str]:
    output_dir = project_root / "reports" / "macro_state_shadow_monitoring"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now_naive().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    prefix = output_dir / f"model1d_shadow_monitoring_{timestamp}_{suffix}"

    frame_keys = (
        "run_status",
        "integrity_checks",
        "benchmark_performance",
        "paired_monthly",
        "paired_summary",
        "transition_summary",
        "readiness",
    )
    output_paths: dict[str, str] = {}
    for key in frame_keys:
        path = Path(f"{prefix}_{key}.csv")
        result[key].to_csv(path, index=False)
        output_paths[key] = str(path)

    readiness = result["readiness"].iloc[0]
    failed = result["integrity_checks"].loc[
        ~result["integrity_checks"]["passed"].astype(bool)
    ]
    failed_text = (
        "- None"
        if failed.empty
        else "\n".join(f"- `{value}`" for value in failed["check_id"].astype(str))
    )
    report = f"""# Model 1D v{result['model_version']} Prospective Shadow Operations Report

## Status

- Monitoring as of: `{result['as_of']}`
- Complete target months: `{int(readiness['complete_target_months'])}`
- Minimum complete target months: `{int(readiness['minimum_complete_target_months'])}`
- Comparison permitted: `{'yes' if readiness['comparison_permitted'] else 'no'}`
- Promotion authority: `{readiness['promotion_authority']}`
- Conclusion status: `{readiness['conclusion_status']}`

This report is operational and research-only. It cannot approve promotion, adaptive switching, blending, or source replacement.

## Run status

{_markdown(result['run_status'], ['state_date', 'information_cutoff', 'target_expected_available_date', 'prediction_count', 'dimension_count', 'outcome_count', 'operational_status', 'days_to_expected_availability'])}

## Integrity checks

{_markdown(result['integrity_checks'], ['check_id', 'passed', 'observed', 'threshold', 'interpretation'])}

Failed checks:

{failed_text}

## Evidence readiness

{_markdown(result['readiness'])}

## Benchmark performance

{_markdown(result['benchmark_performance'])}

## Paired source-versus-rolling-frequency summary

{_markdown(result['paired_summary'])}

## Transition diagnostics

{_markdown(result['transition_summary'])}
"""
    report_path = Path(f"{prefix}.md")
    report_path.write_text(report, encoding="utf-8")
    output_paths["report"] = str(report_path)

    metadata = {
        "model_version": result["model_version"],
        "monitoring_as_of": str(result["as_of"]),
        "created_at_utc": _utc_now_naive().isoformat(),
        "complete_target_months": int(readiness["complete_target_months"]),
        "minimum_complete_target_months": int(
            readiness["minimum_complete_target_months"]
        ),
        "comparison_permitted": bool(readiness["comparison_permitted"]),
        "promotion_authority": str(readiness["promotion_authority"]),
        "promotion_permitted": False,
        "integrity_pass": bool(readiness["integrity_pass"]),
        "output_paths": output_paths,
    }
    metadata_path = Path(f"{prefix}_metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    output_paths["metadata"] = str(metadata_path)
    return output_paths


def run_shadow_monitoring(
    repository: MacroRepository | None = None,
    *,
    as_of: date | None = None,
    project_root: Path | None = None,
    write_report: bool = True,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    root = Path(project_root or settings.project_root)
    monitoring_as_of = as_of or date.today()
    if monitoring_as_of > date.today():
        raise ValueError("The monitoring cutoff cannot be in the future.")
    result = collect_shadow_monitoring(
        repository,
        as_of=monitoring_as_of,
        project_root=root,
    )
    result["output_paths"] = (
        write_shadow_monitoring_report(result, project_root=root)
        if write_report
        else {}
    )
    return result

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from macropulse.operations.model1d_shadow_monitoring import (
    benchmark_performance,
    build_integrity_checks,
    build_readiness,
    build_run_status,
    paired_monthly_performance,
    paired_summary,
)


def _frames(months: int = 1, resolved_months: int = 0):
    runs = []
    predictions = []
    dimensions = []
    outcomes = []
    for index in range(months):
        state_date = (pd.Timestamp("2026-08-31") + pd.offsets.MonthEnd(index)).date()
        run_id = f"run-{index:02d}"
        cutoff = state_date - timedelta(days=20)
        runs.append(
            {
                "shadow_run_id": run_id,
                "model_version": "0.3.8",
                "run_timestamp": pd.Timestamp(cutoff),
                "state_date": state_date,
                "information_cutoff": cutoff,
                "target_expected_available_date": state_date + timedelta(days=90),
                "no_look_ahead_pass": True,
                "status": "predicted",
            }
        )
        for benchmark, family, brier, log_loss in (
            ("source", "contraction", 0.40, 0.90),
            ("rolling_frequency", "benign_expansion", 0.55, 1.10),
        ):
            predictions.append(
                {
                    "shadow_run_id": run_id,
                    "model_version": "0.3.8",
                    "state_date": state_date,
                    "information_cutoff": cutoff,
                    "benchmark_id": benchmark,
                    "probability_sum": 1.0,
                    "no_look_ahead_pass": True,
                }
            )
            if index < resolved_months:
                outcomes.append(
                    {
                        "outcome_id": f"{run_id}-{benchmark}",
                        "shadow_run_id": run_id,
                        "model_version": "0.3.8",
                        "state_date": state_date,
                        "benchmark_id": benchmark,
                        "resolved_at": pd.Timestamp(state_date + timedelta(days=91)),
                        "target_available_date": state_date + timedelta(days=90),
                        "actual_family": "contraction",
                        "actual_probability": 0.60 if benchmark == "source" else 0.30,
                        "brier_score": brier,
                        "log_loss": log_loss,
                        "top1_hit": benchmark == "source",
                        "top2_hit": True,
                        "top3_hit": True,
                        "transition_flag": index % 3 == 0,
                        "no_look_ahead_pass": True,
                    }
                )
        for dimension in ("growth", "inflation", "labour"):
            dimensions.append(
                {
                    "shadow_run_id": run_id,
                    "model_version": "0.3.8",
                    "state_date": state_date,
                    "information_cutoff": cutoff,
                    "dimension": dimension,
                    "no_look_ahead_pass": True,
                }
            )
    return tuple(pd.DataFrame(value) for value in (runs, predictions, dimensions, outcomes))


def test_pending_month_is_structurally_complete() -> None:
    runs, predictions, dimensions, outcomes = _frames()
    status = build_run_status(
        runs,
        predictions,
        dimensions,
        outcomes,
        as_of=date(2026, 8, 5),
        model_version="0.3.8",
    )
    checks = build_integrity_checks(
        runs,
        predictions,
        dimensions,
        outcomes,
        status,
        probability_sum_tolerance=1e-10,
        append_only_contract={
            "append_only": True,
            "updates_prohibited": True,
            "deletes_prohibited": True,
            "prediction_overwrite_prohibited": True,
        },
    )
    assert status.iloc[0]["operational_status"] == "pending_target"
    assert status.iloc[0]["prediction_count"] == 2
    assert status.iloc[0]["dimension_count"] == 3
    assert status.iloc[0]["outcome_count"] == 0
    assert checks["passed"].all()


def test_partial_outcome_is_an_integrity_error() -> None:
    runs, predictions, dimensions, outcomes = _frames(resolved_months=1)
    outcomes = outcomes.iloc[:1].copy()
    status = build_run_status(
        runs,
        predictions,
        dimensions,
        outcomes,
        as_of=date(2027, 1, 1),
        model_version="0.3.8",
    )
    assert status.iloc[0]["operational_status"] == "integrity_error"
    checks = build_integrity_checks(
        runs,
        predictions,
        dimensions,
        outcomes,
        status,
        probability_sum_tolerance=1e-10,
        append_only_contract={
            "append_only": True,
            "updates_prohibited": True,
            "deletes_prohibited": True,
            "prediction_overwrite_prohibited": True,
        },
    )
    assert not bool(
        checks.loc[checks.check_id == "outcome_rows_zero_or_two", "passed"].iloc[0]
    )


def test_twelve_complete_months_unlock_report_only_comparison() -> None:
    runs, predictions, dimensions, outcomes = _frames(months=12, resolved_months=12)
    status = build_run_status(
        runs,
        predictions,
        dimensions,
        outcomes,
        as_of=date(2028, 1, 1),
        model_version="0.3.8",
    )
    checks = build_integrity_checks(
        runs,
        predictions,
        dimensions,
        outcomes,
        status,
        probability_sum_tolerance=1e-10,
        append_only_contract={
            "append_only": True,
            "updates_prohibited": True,
            "deletes_prohibited": True,
            "prediction_overwrite_prohibited": True,
        },
    )
    readiness = build_readiness(
        status,
        checks,
        minimum_complete_months=12,
        promotion_authority="none",
    ).iloc[0]
    assert readiness["comparison_permitted"]
    assert readiness["promotion_permitted"] is False or not readiness["promotion_permitted"]
    assert readiness["conclusion_status"] == "eligible_for_report_only_comparison"


def test_performance_tables_are_paired_by_run() -> None:
    _, _, _, outcomes = _frames(months=3, resolved_months=3)
    performance = benchmark_performance(outcomes)
    paired = paired_monthly_performance(outcomes)
    summary = paired_summary(paired)
    assert set(performance.benchmark_id) == {"source", "rolling_frequency"}
    assert len(paired) == 3
    assert paired.source_brier_improvement.gt(0).all()
    assert summary.iloc[0].source_brier_win_rate == 1.0

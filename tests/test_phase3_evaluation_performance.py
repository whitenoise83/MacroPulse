from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from macropulse.evaluation.performance import (
    build_horizon_metrics,
    build_stage_metrics,
    build_target_metrics,
    horizon_bucket,
    serialise_performance_report,
)


def row(
    *,
    component="1C",
    target_series="PAYEMS",
    target_name="Nonfarm Payroll Change",
    cutoff=date(2026, 1, 1),
    forecast=10.0,
    outcome=8.0,
    lower=0.0,
    upper=20.0,
    interval_covered=True,
    lead_days=7,
    stage="late_month",
    run_id="run",
):
    signed = forecast - outcome
    return {
        "evaluation_status": "resolved",
        "no_look_ahead_pass": True,
        "component": component,
        "target_series": target_series,
        "target_name": target_name,
        "information_cutoff": cutoff,
        "target_period": cutoff.strftime("%Y-%m"),
        "run_id": run_id,
        "forecast_value": forecast,
        "outcome_value": outcome,
        "absolute_error": abs(signed),
        "signed_error": signed,
        "squared_error": signed**2,
        "interval_covered": interval_covered,
        "interval_width": upper - lower,
        "lead_days": lead_days,
        "forecast_stage": stage,
    }


def test_target_metrics_calculate_accuracy_and_calibration() -> None:
    ledger = pd.DataFrame(
        [
            row(
                cutoff=date(2026, 1, 1),
                forecast=10,
                outcome=8,
                run_id="a",
            ),
            row(
                cutoff=date(2026, 2, 1),
                forecast=6,
                outcome=8,
                interval_covered=False,
                run_id="b",
            ),
        ]
    )
    result = build_target_metrics(ledger)
    assert len(result) == 1
    metric = result.iloc[0]
    assert metric["n_resolved"] == 2
    assert metric["mae"] == pytest.approx(2.0)
    assert metric["rmse"] == pytest.approx(2.0)
    assert metric["bias"] == pytest.approx(0.0)
    assert metric["median_absolute_error"] == pytest.approx(2.0)
    assert metric["interval_coverage_80"] == pytest.approx(0.5)
    assert metric["coverage_gap_vs_nominal_80"] == pytest.approx(-0.3)
    assert metric["directional_accuracy"] == pytest.approx(1.0)
    assert metric["sample_status"] == "insufficient_for_interpretation"


def test_unresolved_and_invalid_rows_are_not_scored() -> None:
    valid = row(run_id="valid")
    unresolved = row(run_id="pending")
    unresolved["evaluation_status"] = "unresolved_outcome_not_yet_available"
    invalid = row(run_id="invalid")
    invalid["evaluation_status"] = "invalid_no_look_ahead"
    invalid["no_look_ahead_pass"] = False

    result = build_target_metrics(
        pd.DataFrame([valid, unresolved, invalid])
    )
    assert result.iloc[0]["n_resolved"] == 1


def test_raw_error_metrics_are_never_pooled_across_targets() -> None:
    ledger = pd.DataFrame(
        [
            row(
                target_series="PAYEMS",
                target_name="Nonfarm Payroll Change",
                forecast=100,
                outcome=0,
                run_id="payems",
            ),
            row(
                target_series="UNRATE",
                target_name="Unemployment Rate",
                forecast=4.2,
                outcome=4.1,
                run_id="unrate",
            ),
        ]
    )
    result = build_target_metrics(ledger)
    assert len(result) == 2
    assert set(result["target_series"]) == {"PAYEMS", "UNRATE"}


def test_level_target_has_no_directional_accuracy() -> None:
    ledger = pd.DataFrame(
        [
            row(
                target_series="UNRATE",
                target_name="Unemployment Rate",
                forecast=4.2,
                outcome=4.1,
                run_id="unrate",
            )
        ]
    )
    result = build_target_metrics(ledger)
    metric = result.iloc[0]
    assert metric["n_direction"] == 0
    assert pd.isna(metric["directional_accuracy"])


@pytest.mark.parametrize(
    ("lead", "expected"),
    [
        (0, "0-7d"),
        (7, "0-7d"),
        (8, "8-14d"),
        (14, "8-14d"),
        (15, "15-30d"),
        (30, "15-30d"),
        (31, "31-60d"),
        (60, "31-60d"),
        (61, "61+d"),
        (None, "UNKNOWN"),
        (-1, "INVALID_NEGATIVE"),
    ],
)
def test_horizon_bucket_boundaries(lead, expected) -> None:
    assert horizon_bucket(lead) == expected


def test_stage_and_horizon_breakdowns_remain_target_specific() -> None:
    ledger = pd.DataFrame(
        [
            row(stage="early_month", lead_days=20, run_id="a"),
            row(
                cutoff=date(2026, 2, 1),
                stage="late_month",
                lead_days=5,
                run_id="b",
            ),
        ]
    )
    stage = build_stage_metrics(ledger)
    horizon = build_horizon_metrics(ledger)
    assert set(stage["forecast_stage"]) == {"early_month", "late_month"}
    assert set(horizon["horizon_bucket"]) == {"0-7d", "15-30d"}


def test_serialised_report_is_null_safe_and_declares_policy() -> None:
    ledger = pd.DataFrame(
        [
            row(
                target_series="UNRATE",
                target_name="Unemployment Rate",
                forecast=4.2,
                outcome=4.1,
                run_id="unrate",
            )
        ]
    )
    payload = serialise_performance_report(
        ledger,
        as_of=date(2026, 1, 15),
    )
    assert payload["schema_version"] == "1.0.0"
    assert payload["policy"]["cross_target_raw_error_pooling"] is False
    assert payload["policy"]["automatic_model_action"] is False
    assert payload["policy"]["model1d_included"] is False
    assert payload["target_metrics"][0]["directional_accuracy"] is None

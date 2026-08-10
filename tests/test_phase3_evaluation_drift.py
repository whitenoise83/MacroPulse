from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from macropulse.evaluation.performance import (
    DRIFT_RECENT_N,
    DRIFT_REFERENCE_N,
    MIN_INTERPRETATION_N,
    build_drift_metrics,
    build_target_metrics,
)


def ledger_with_errors(errors):
    start = date(2025, 1, 1)
    rows = []
    for index, error in enumerate(errors):
        cutoff = start + timedelta(days=30 * index)
        outcome = 10.0
        forecast = outcome + error
        rows.append(
            {
                "evaluation_status": "resolved",
                "no_look_ahead_pass": True,
                "component": "1B",
                "target_series": "CPIAUCSL",
                "target_name": "Headline CPI",
                "information_cutoff": cutoff,
                "target_period": cutoff.strftime("%Y-%m"),
                "run_id": f"run-{index:02d}",
                "forecast_value": forecast,
                "outcome_value": outcome,
                "absolute_error": abs(error),
                "signed_error": error,
                "squared_error": error**2,
                "interval_covered": True,
                "interval_width": 4.0,
                "lead_days": 10,
                "forecast_stage": "late_month",
            }
        )
    return pd.DataFrame(rows)


def test_target_sample_status_changes_at_documented_minimum() -> None:
    low = build_target_metrics(
        ledger_with_errors([1.0] * (MIN_INTERPRETATION_N - 1))
    )
    ready = build_target_metrics(
        ledger_with_errors([1.0] * MIN_INTERPRETATION_N)
    )
    assert low.iloc[0]["sample_status"] == "insufficient_for_interpretation"
    assert ready.iloc[0]["sample_status"] == "descriptive_ready"


def test_drift_is_insufficient_before_required_history() -> None:
    required = DRIFT_RECENT_N + DRIFT_REFERENCE_N
    result = build_drift_metrics(
        ledger_with_errors([1.0] * (required - 1))
    )
    metric = result.iloc[0]
    assert metric["drift_status"] == "insufficient_sample"
    assert metric["required_resolved"] == required
    assert pd.isna(metric["mae_ratio_recent_to_reference"])


def test_drift_compares_latest_four_with_preceding_eight() -> None:
    reference_errors = [1.0] * DRIFT_REFERENCE_N
    recent_errors = [2.0] * DRIFT_RECENT_N
    result = build_drift_metrics(
        ledger_with_errors(reference_errors + recent_errors)
    )
    metric = result.iloc[0]
    assert metric["drift_status"] == "descriptive_available"
    assert metric["reference_n"] == DRIFT_REFERENCE_N
    assert metric["recent_n"] == DRIFT_RECENT_N
    assert metric["reference_mae"] == pytest.approx(1.0)
    assert metric["recent_mae"] == pytest.approx(2.0)
    assert metric["mae_ratio_recent_to_reference"] == pytest.approx(2.0)
    assert metric["bias_shift"] == pytest.approx(1.0)
    assert metric["coverage_shift"] == pytest.approx(0.0)


def test_zero_reference_mae_does_not_create_infinite_ratio() -> None:
    result = build_drift_metrics(
        ledger_with_errors(
            [0.0] * DRIFT_REFERENCE_N
            + [1.0] * DRIFT_RECENT_N
        )
    )
    assert pd.isna(
        result.iloc[0]["mae_ratio_recent_to_reference"]
    )

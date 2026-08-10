from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from macropulse.evaluation.ledger import (
    OUTCOME_DEFINITION,
    OUTCOME_VINTAGE,
    OutcomeResolution,
    TargetSpec,
    _actual_from_release_snapshot,
    _evaluate_row,
    serialise_forecast_evaluation,
    summarise_forecast_evaluation,
)


def forecast_row(**overrides):
    values = {
        "component": "1B",
        "model_id": "US_INFLATION_NOWCAST_1B",
        "model_version": "1.0.0",
        "run_id": "run-1",
        "information_cutoff": date(2026, 1, 31),
        "data_as_of": date(2026, 1, 30),
        "target_series": "CPIAUCSL",
        "target_name": "Headline CPI",
        "target_period": "2026-01",
        "forecast_stage": "late_month",
        "forecast_model_name": "stable",
        "forecast_value": 3.0,
        "lower_80": 1.0,
        "upper_80": 4.0,
        "estimated_release_date": date(2026, 2, 12),
    }
    values.update(overrides)
    return pd.Series(values)


def test_signed_error_is_forecast_minus_outcome() -> None:
    row = _evaluate_row(
        forecast_row(forecast_value=3.0),
        resolution=OutcomeResolution(
            status="resolved",
            detail="ok",
            release_date=date(2026, 2, 12),
            value=2.5,
        ),
        as_of=date(2026, 2, 12),
    )
    assert row["signed_error"] == pytest.approx(0.5)
    assert row["absolute_error"] == pytest.approx(0.5)
    assert row["squared_error"] == pytest.approx(0.25)
    assert row["interval_covered"] is True
    assert row["no_look_ahead_pass"] is True
    assert row["lead_days"] == 12


def test_same_day_cutoff_fails_closed() -> None:
    row = _evaluate_row(
        forecast_row(information_cutoff=date(2026, 2, 12)),
        resolution=OutcomeResolution(
            status="resolved",
            detail="ok",
            release_date=date(2026, 2, 12),
            value=2.5,
        ),
        as_of=date(2026, 2, 12),
    )
    assert row["evaluation_status"] == "invalid_no_look_ahead"
    assert row["no_look_ahead_pass"] is False
    assert row["signed_error"] is None
    assert row["outcome_value"] is None


def test_unresolved_rows_do_not_receive_error_metrics() -> None:
    row = _evaluate_row(
        forecast_row(),
        resolution=OutcomeResolution(
            status="unresolved_release_snapshot_not_cached",
            detail="missing",
            release_date=date(2026, 2, 12),
            value=None,
        ),
        as_of=date(2026, 2, 12),
    )
    assert row["signed_error"] is None
    assert row["absolute_error"] is None
    assert row["squared_error"] is None
    assert row["interval_covered"] is None


def test_monthly_first_release_transform_uses_governed_transform() -> None:
    snapshot = pd.DataFrame(
        {
            "series_id": ["CPIAUCSL", "CPIAUCSL"],
            "observation_date": ["2025-12-01", "2026-01-01"],
            "value": [100.0, 101.0],
        }
    )
    target = TargetSpec(
        component="1B",
        series_id="CPIAUCSL",
        name="Headline CPI",
        frequency="M",
        transform="annualised_mom_log",
        start_date="2000-01-01",
    )
    value = _actual_from_release_snapshot(
        snapshot,
        target=target,
        target_period=pd.Period("2026-01", freq="M"),
    )
    assert value > 0.0


def test_summary_does_not_compute_phase3c_accuracy_statistics() -> None:
    ledger = pd.DataFrame(
        [
            _evaluate_row(
                forecast_row(run_id="resolved"),
                resolution=OutcomeResolution(
                    status="resolved",
                    detail="ok",
                    release_date=date(2026, 2, 12),
                    value=2.5,
                ),
                as_of=date(2026, 2, 12),
            ),
            _evaluate_row(
                forecast_row(run_id="pending", target_period="2026-02"),
                resolution=OutcomeResolution(
                    status="unresolved_release_not_recorded",
                    detail="pending",
                    release_date=None,
                    value=None,
                ),
                as_of=date(2026, 2, 12),
            ),
        ]
    )
    summary = summarise_forecast_evaluation(
        ledger,
        as_of=date(2026, 2, 12),
    )
    assert summary["forecast_rows"] == 2
    assert summary["resolved_rows"] == 1
    assert summary["unresolved_rows"] == 1
    assert "mae" not in summary
    assert summary["signed_error_convention"] == "forecast_minus_outcome"


def test_json_serialisation_is_null_safe_and_declares_vintage() -> None:
    ledger = pd.DataFrame(
        [
            _evaluate_row(
                forecast_row(),
                resolution=OutcomeResolution(
                    status="unresolved_release_not_recorded",
                    detail="pending",
                    release_date=None,
                    value=None,
                ),
                as_of=date(2026, 2, 1),
            )
        ]
    )
    payload = serialise_forecast_evaluation(
        ledger,
        as_of=date(2026, 2, 1),
    )
    assert payload["schema_version"] == "1.0.0"
    assert payload["summary"]["outcome_vintage"] == OUTCOME_VINTAGE
    assert payload["summary"]["outcome_definition"] == OUTCOME_DEFINITION
    assert payload["ledger"][0]["outcome_value"] is None

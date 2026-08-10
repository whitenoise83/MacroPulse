from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from macropulse.evaluation.revisions import build_revision_table


def forecast(
    *,
    component="1B",
    run_id="run-a",
    cutoff=date(2026, 8, 1),
    target_series="CPIAUCSL",
    target_period="2026-07",
    value=1.0,
    stage="month_end",
):
    return {
        "component": component,
        "run_id": run_id,
        "model_id": (
            "US_INFLATION_NOWCAST_1B"
            if component == "1B"
            else "US_GDP_NOWCAST_1A"
        ),
        "model_version": "1.0.0",
        "information_cutoff": cutoff,
        "data_as_of": cutoff,
        "target_series": target_series,
        "target_name": target_series,
        "target_period": target_period,
        "forecast_stage": stage,
        "forecast_model_name": "stable",
        "forecast_value": value,
        "lower_80": value - 1,
        "upper_80": value + 1,
        "estimated_release_date": None,
        "created_at": pd.Timestamp(cutoff),
    }


def test_same_target_period_builds_sequential_revision() -> None:
    frame = pd.DataFrame(
        [
            forecast(run_id="a", value=1.0),
            forecast(
                run_id="b",
                cutoff=date(2026, 8, 8),
                value=1.25,
            ),
        ]
    )
    result = build_revision_table(frame)

    assert len(result) == 2
    assert result.iloc[0]["comparison_status"] == "baseline_no_previous"
    current = result.iloc[1]
    assert current["comparison_status"] == "comparable_revision"
    assert current["revision"] == pytest.approx(0.25)
    assert current["absolute_revision"] == pytest.approx(0.25)
    assert current["revision_direction"] == "upward"
    assert current["cumulative_revision"] == pytest.approx(0.25)
    assert current["days_between_runs"] == 7


def test_target_period_change_is_not_revision() -> None:
    frame = pd.DataFrame(
        [
            forecast(
                component="1A",
                run_id="q2",
                cutoff=date(2026, 7, 29),
                target_series="GDPC1",
                target_period="2026Q2",
                value=2.7,
            ),
            forecast(
                component="1A",
                run_id="q3",
                cutoff=date(2026, 8, 8),
                target_series="GDPC1",
                target_period="2026Q3",
                value=2.4,
            ),
        ]
    )
    result = build_revision_table(frame)
    assert len(result) == 2
    assert set(result["comparison_status"]) == {"baseline_no_previous"}
    assert result["revision"].isna().all()


def test_cumulative_revision_uses_first_comparable_forecast() -> None:
    frame = pd.DataFrame(
        [
            forecast(run_id="a", value=1.0),
            forecast(
                run_id="b",
                cutoff=date(2026, 8, 4),
                value=1.5,
            ),
            forecast(
                run_id="c",
                cutoff=date(2026, 8, 8),
                value=1.25,
            ),
        ]
    )
    result = build_revision_table(frame)
    final = result.iloc[-1]
    assert final["revision"] == pytest.approx(-0.25)
    assert final["cumulative_revision"] == pytest.approx(0.25)


def test_same_cutoff_order_is_deterministic_from_created_at_then_run_id() -> None:
    first = forecast(run_id="z", value=1.0)
    second = forecast(run_id="a", value=1.2)
    first["created_at"] = pd.Timestamp("2026-08-01 09:00")
    second["created_at"] = pd.Timestamp("2026-08-01 10:00")

    result = build_revision_table(pd.DataFrame([second, first]))
    assert result.iloc[0]["current_run_id"] == "z"
    assert result.iloc[1]["previous_run_id"] == "z"
    assert result.iloc[1]["current_run_id"] == "a"

from __future__ import annotations

from datetime import date
import pandas as pd
import pytest
from macropulse.evaluation.ledger import OutcomeResolution, _evaluate_row

def forecast_row(cutoff: date) -> pd.Series:
    return pd.Series({
        "component": "1A",
        "model_id": "US_GDP_NOWCAST_1A", "model_version": "1.0.0",
        "run_id": "run", "information_cutoff": cutoff, "data_as_of": cutoff,
        "target_series": "GDPC1", "target_name": "Real Gross Domestic Product",
        "target_period": "2026Q2", "forecast_stage": "quarter_end",
        "forecast_model_name": "stable", "forecast_value": 2.0,
        "lower_80": 0.0, "upper_80": 4.0,
        "estimated_release_date": date(2026, 7, 30),
    })

def resolved(release_date: date) -> OutcomeResolution:
    return OutcomeResolution(
        status="resolved", detail="fixture", release_date=release_date,
        value=1.5, evidence_source="historical_snapshots.release_date",
    )

def test_forecast_before_release_can_be_scored() -> None:
    result = _evaluate_row(
        forecast_row(date(2026, 7, 29)),
        resolution=resolved(date(2026, 7, 30)),
        as_of=date(2026, 8, 1),
    )
    assert result["evaluation_status"] == "resolved"
    assert result["no_look_ahead_pass"] is True
    assert result["lead_days"] == 1
    assert result["signed_error"] == pytest.approx(0.5)

@pytest.mark.parametrize("cutoff", [date(2026, 7, 30), date(2026, 7, 31)])
def test_same_day_or_post_release_forecast_fails_closed(cutoff: date) -> None:
    result = _evaluate_row(
        forecast_row(cutoff),
        resolution=resolved(date(2026, 7, 30)),
        as_of=date(2026, 8, 1),
    )
    assert result["evaluation_status"] == "invalid_no_look_ahead"
    assert result["no_look_ahead_pass"] is False
    assert result["outcome_value"] is None
    assert result["signed_error"] is None
    assert result["absolute_error"] is None
    assert result["squared_error"] is None

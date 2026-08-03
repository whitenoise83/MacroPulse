from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.target_validity import run_target_validity_audit
from macropulse.macro_state.tournament import REGIME_FAMILY, classify_regime_with_thresholds
from macropulse.macro_state.versioning import load_macro_state_governance


def _monthly() -> pd.DataFrame:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    dates = pd.date_range("2020-01-31", periods=36, freq="ME").date
    rows = []
    for index, state_date in enumerate(dates):
        actual_growth = float(np.sin(index / 3.0))
        actual_inflation = float(np.cos(index / 4.0))
        actual_labour = float(np.sin(index / 5.0))
        forecast_growth = actual_growth + 0.20
        forecast_inflation = actual_inflation - 0.10
        forecast_labour = actual_labour - 0.15
        actual_regime = classify_regime_with_thresholds(
            actual_growth, actual_inflation, actual_labour, thresholds
        )
        forecast_regime = classify_regime_with_thresholds(
            forecast_growth, forecast_inflation, forecast_labour, thresholds
        )
        rows.append(
            {
                "state_date": state_date,
                "forecast_growth": forecast_growth,
                "forecast_inflation": forecast_inflation,
                "forecast_labour": forecast_labour,
                "actual_growth": actual_growth,
                "actual_inflation": actual_inflation,
                "actual_labour": actual_labour,
                "forecast_regime": forecast_regime,
                "actual_regime": actual_regime,
                "forecast_family": REGIME_FAMILY[forecast_regime],
                "actual_family": REGIME_FAMILY[actual_regime],
            }
        )
    return pd.DataFrame(rows)


def _lineage(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state_date in monthly["state_date"]:
        for target in ("GDPC1", "CPIAUCSL", "UNRATE"):
            rows.append(
                {
                    "state_date": state_date,
                    "source_target": target,
                    "target_period": (
                        str(pd.Period(state_date, freq="Q"))
                        if target == "GDPC1"
                        else str(pd.Period(state_date, freq="M"))
                    ),
                    "information_cutoff": state_date,
                    "data_as_of": state_date,
                    "max_observation_date": state_date,
                    "actual_release_date": None,
                    "target_leakage": False,
                }
            )
    return pd.DataFrame(rows)


def test_target_validity_pipeline_produces_all_evidence_tables() -> None:
    config = load_macro_state_governance()
    monthly = _monthly()
    dates = tuple(monthly["state_date"])
    plan = RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:18], dates[18:24]),
            RollingFold("fold_02", dates[:21], dates[21:27]),
        ),
        selection_dates=dates[:27],
        audit_dates=dates[27:],
    )
    core = {
        "thresholds": config["tournament"]["threshold_candidates"]["sensitive"]
    }
    result = run_target_validity_audit(
        monthly, plan, core, _lineage(monthly), config
    )
    assert len(result["benchmark_summary"]) == 6
    assert len(result["benchmark_fold_metrics"]) == 12
    assert len(result["audit_benchmarks"]) == 6
    assert len(result["validity_flags"]) == 10
    assert result["target_validity_pass"] is False
    assert set(result["validity_flags"]["check_id"]).issuperset(
        {"actual_revision_vintage_recorded", "source_beats_naive_baseline"}
    )

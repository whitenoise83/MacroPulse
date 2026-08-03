from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from macropulse.macro_state.hierarchical_diagnostics import (
    run_hierarchical_diagnostics,
)
from macropulse.macro_state.rolling_tournament import (
    RollingFold,
    RollingTournamentPlan,
)
from macropulse.macro_state.tournament import (
    REGIME_FAMILY,
    classify_regime_with_thresholds,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _monthly() -> pd.DataFrame:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    dates = pd.date_range("2020-01-31", periods=24, freq="ME").date
    rows = []
    for index, state_date in enumerate(dates):
        actual_growth = np.sin(index / 3.0)
        actual_inflation = np.cos(index / 4.0)
        actual_labour = np.sin(index / 5.0)
        forecast_growth = actual_growth + 0.35
        forecast_inflation = actual_inflation - 0.10
        forecast_labour = actual_labour - 0.25
        actual_regime = classify_regime_with_thresholds(
            actual_growth,
            actual_inflation,
            actual_labour,
            thresholds,
        )
        forecast_regime = classify_regime_with_thresholds(
            forecast_growth,
            forecast_inflation,
            forecast_labour,
            thresholds,
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
                "growth_lower": forecast_growth - 0.4,
                "growth_upper": forecast_growth + 0.4,
                "inflation_lower": forecast_inflation - 0.4,
                "inflation_upper": forecast_inflation + 0.4,
                "labour_lower": forecast_labour - 0.4,
                "labour_upper": forecast_labour + 0.4,
                "forecast_regime": forecast_regime,
                "actual_regime": actual_regime,
                "forecast_family": REGIME_FAMILY[forecast_regime],
                "actual_family": REGIME_FAMILY[actual_regime],
            }
        )
    return pd.DataFrame(rows)


def test_pipeline_evaluates_nine_candidates_across_folds() -> None:
    config = load_macro_state_governance()
    config = {**config}
    config["hierarchical_diagnostics"] = {
        **config["hierarchical_diagnostics"],
        "bootstrap_repetitions": 50,
    }
    monthly = _monthly()
    dates = tuple(monthly["state_date"])
    plan = RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:12], dates[12:18]),
            RollingFold("fold_02", dates[:15], dates[15:21]),
        ),
        selection_dates=dates[:21],
        audit_dates=dates[21:],
    )
    core = {
        "thresholds": config["tournament"]["threshold_candidates"][
            "sensitive"
        ]
    }
    result = run_hierarchical_diagnostics(monthly, plan, core, config)
    assert len(result["stability"]) == 9
    assert len(result["fold_metrics"]) == 18
    assert len(result["audit"]) == 9
    assert result["selected_candidate_id"] in set(
        result["stability"]["candidate_id"]
    )
    assert result["stability"]["stability_rank"].min() == 1

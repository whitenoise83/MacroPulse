from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import (
    attach_bootstrap_intervals,
    run_rolling_core_tournament,
    run_rolling_uncertainty_tournament,
    selected_subperiod_metrics,
)
from macropulse.macro_state.versioning import load_macro_state_governance


TARGETS = {
    "GDPC1": (2.0, 1.0, "Q"),
    "PCEPILFE": (2.0, 0.6, "M"),
    "CPILFESL": (2.3, 0.7, "M"),
    "PCEPI": (2.0, 0.8, "M"),
    "CPIAUCSL": (2.3, 0.9, "M"),
    "PAYEMS": (100.0, 45.0, "M"),
    "UNRATE": (4.5, 0.4, "M"),
    "CES0500000003": (3.3, 0.5, "M"),
}


def _synthetic_dataset() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2020-02-29", periods=73, freq="ME")
    for index, state_date in enumerate(dates):
        cycle = np.sin(index / 5.0)
        for target, (center, scale, frequency) in TARGETS.items():
            orientation = -1.0 if target == "UNRATE" else 1.0
            actual = center + orientation * scale * cycle
            point = actual + orientation * scale * 0.15 * np.cos(index / 3.0)
            period = pd.Period(state_date, freq=frequency)
            rows.append(
                {
                    "state_date": state_date.date(),
                    "source_target": target,
                    "target_period": str(period),
                    "target_period_ordinal": int(period.ordinal),
                    "point_forecast": point,
                    "lower_80": point - abs(scale),
                    "upper_80": point + abs(scale),
                    "actual": actual,
                }
            )
    return pd.DataFrame(rows)


def test_full_rolling_origin_pipeline_runs() -> None:
    config = copy.deepcopy(load_macro_state_governance())
    config["stability_tournament"]["top_core_candidates"] = 1
    config["stability_tournament"]["bootstrap_repetitions"] = 30
    config["tournament"]["uncertainty_draws"] = 16
    config["tournament"]["normalization_candidates"] = {
        "policy_anchors": config["tournament"]["normalization_candidates"]["policy_anchors"]
    }
    config["tournament"]["inflation_weight_candidates"] = {
        "policy": config["tournament"]["inflation_weight_candidates"]["policy"]
    }
    config["tournament"]["labour_weight_candidates"] = {
        "policy": config["tournament"]["labour_weight_candidates"]["policy"]
    }
    config["tournament"]["threshold_candidates"] = {
        "baseline": config["tournament"]["threshold_candidates"]["baseline"]
    }
    dataset = _synthetic_dataset()
    (
        plan,
        candidates,
        monthly_by_candidate,
        core_fold_metrics,
        core_stability,
    ) = run_rolling_core_tournament(dataset, config)
    assert len(plan.folds) == 7
    assert len(candidates) == 1
    assert len(monthly_by_candidate) == 1
    assert len(core_fold_metrics) == 7
    assert len(core_stability) == 1

    (
        final_stability,
        final_fold_metrics,
        monthly_final,
        audit,
    ) = run_rolling_uncertainty_tournament(
        core_candidates=candidates,
        monthly_by_candidate=monthly_by_candidate,
        core_fold_metrics=core_fold_metrics,
        core_stability=core_stability,
        plan=plan,
        config=config,
    )
    assert len(final_stability) == 3
    assert len(final_fold_metrics) == 3 * 7
    assert len(monthly_final) == 3
    assert len(audit) == 3
    assert int(final_stability["stability_rank"].min()) == 1
    assert int(audit["audit_final_rank"].min()) == 1

    bootstrapped = attach_bootstrap_intervals(
        final_stability,
        final_fold_metrics=final_fold_metrics,
        monthly_final=monthly_final,
        plan=plan,
        config=config,
    )
    assert bootstrapped["bootstrap_margin_lower"].notna().all()
    selected_id = str(bootstrapped.iloc[0]["candidate_id"])
    subperiods = selected_subperiod_metrics(
        monthly_final[selected_id], config
    )
    assert set(subperiods["subperiod_id"]) == {
        "pandemic_reopening",
        "inflation_acceleration",
        "disinflation_late_cycle",
        "recent_reflation_risk",
    }

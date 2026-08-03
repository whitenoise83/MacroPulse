from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from macropulse.macro_state.rolling_tournament import (
    RollingFold,
    block_bootstrap_margin_ci,
    candidate_fold_baseline,
    rolling_origin_plan,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def test_rolling_origin_plan_reserves_consumed_audit() -> None:
    dates = pd.date_range("2020-02-29", periods=73, freq="ME").date
    plan = rolling_origin_plan(
        dates,
        minimum_training_months=30,
        evaluation_months=6,
        step_months=3,
        audit_months=19,
        minimum_folds=7,
    )
    assert len(plan.selection_dates) == 54
    assert len(plan.audit_dates) == 19
    assert len(plan.folds) == 7
    assert len(plan.folds[0].training_dates) == 30
    assert len(plan.folds[-1].training_dates) == 48
    assert plan.folds[-1].evaluation_dates[-1] == plan.selection_dates[-1]
    assert plan.audit_dates[0] > plan.selection_dates[-1]


def test_candidate_fold_baseline_uses_prior_training_mode_and_persistence() -> None:
    dates = pd.date_range("2023-01-31", periods=8, freq="ME").date
    monthly = pd.DataFrame(
        {
            "state_date": dates,
            "actual_regime": [
                "reflation",
                "reflation",
                "mixed_transition",
                "reflation",
                "reflation",
                "overheating",
                "overheating",
                "overheating",
            ],
            "forecast_regime": [
                "reflation",
                "reflation",
                "reflation",
                "reflation",
                "reflation",
                "overheating",
                "overheating",
                "reflation",
            ],
        }
    )
    fold = RollingFold(
        fold_id="fold_01",
        training_dates=tuple(dates[:4]),
        evaluation_dates=tuple(dates[4:]),
    )
    result = candidate_fold_baseline(monthly, fold)
    assert result["training_mode_regime"] == "reflation"
    assert result["mode_accuracy"] == 0.25
    assert result["persistence_accuracy"] == 0.75
    assert result["strongest_baseline"] == "persistence"


def test_block_bootstrap_margin_is_deterministic() -> None:
    differences = [
        np.asarray([1.0, 0.0, -1.0, 1.0, 0.0, 1.0]),
        np.asarray([0.0, 1.0, 0.0, -1.0, 1.0, 1.0]),
    ]
    first = block_bootstrap_margin_ci(
        differences,
        repetitions=200,
        block_months=3,
        confidence=0.90,
        seed=13031,
    )
    second = block_bootstrap_margin_ci(
        differences,
        repetitions=200,
        block_months=3,
        confidence=0.90,
        seed=13031,
    )
    assert first == second
    assert first["bootstrap_margin_lower"] <= first["bootstrap_margin_mean"]
    assert first["bootstrap_margin_mean"] <= first["bootstrap_margin_upper"]


def test_model_identity_is_v035() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.5"
    assert config["stability_tournament"]["minimum_folds"] == 7
    assert config["stability_tournament"]["audit_months"] == 19

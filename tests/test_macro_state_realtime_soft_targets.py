from __future__ import annotations

import json
from datetime import date

import pandas as pd

from macropulse.macro_state.realtime_soft_targets import (
    _target_actual_from_frame,
    family_probabilities_from_regimes,
    prospective_shadow_status,
    soft_actual_distribution,
    soft_target_plan,
)
from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.versioning import load_macro_state_governance


def test_soft_target_plan_is_prespecified() -> None:
    config = load_macro_state_governance()
    plan = soft_target_plan(config)
    assert plan.target_modes == (
        "initial_release",
        "fixed_horizon_90d",
        "latest_revised",
    )
    assert plan.fixed_horizon_days == 90
    assert plan.threshold_ids == ("sensitive", "baseline", "conservative")
    assert plan.prospective_shadow_start == date(2026, 4, 30)


def test_latest_level_actual_uses_requested_target_month() -> None:
    frame = pd.DataFrame(
        {
            "series_id": ["UNRATE", "UNRATE", "UNRATE"],
            "observation_date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "value": [3.7, 3.9, 4.2],
        }
    )
    value = _target_actual_from_frame(
        frame, target="UNRATE", target_period="2024-03"
    )
    assert value == 4.2


def test_family_probabilities_aggregate_regime_mass() -> None:
    probabilities = {
        "hard_landing_risk": 0.20,
        "demand_slowdown": 0.15,
        "stagflation_risk": 0.10,
        "overheating": 0.10,
        "reflation": 0.05,
        "balanced_expansion": 0.20,
        "disinflationary_expansion": 0.15,
        "mixed_transition": 0.05,
    }
    families = family_probabilities_from_regimes(probabilities)
    assert abs(families["contraction"] - 0.35) < 1e-12
    assert abs(families["benign_expansion"] - 0.35) < 1e-12
    assert abs(sum(families.values()) - 1.0) < 1e-12


def test_soft_target_marks_boundary_case_less_confident() -> None:
    config = load_macro_state_governance()
    stable = soft_actual_distribution(1.8, -1.8, 1.8, config)
    boundary = soft_actual_distribution(0.50, 0.50, 0.25, config)
    assert stable["family_top_probability"] > boundary["family_top_probability"]
    assert stable["family_probability_margin"] > boundary["family_probability_margin"]
    assert json.loads(stable["family_probabilities_json"])


def test_prospective_shadow_is_not_inside_historical_plan() -> None:
    config = load_macro_state_governance()
    dates = tuple(pd.date_range("2023-01-31", periods=36, freq="ME").date)
    plan = RollingTournamentPlan(
        folds=(RollingFold("fold_01", dates[:24], dates[24:30]),),
        selection_dates=dates[:30],
        audit_dates=dates[30:],
    )
    source = pd.DataFrame({"state_date": dates})
    result = prospective_shadow_status(source, plan, config).iloc[0]
    assert bool(result["prospective_isolation_pass"])
    assert result["available_shadow_months"] == 0


def test_model_identity_is_v036() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.6"

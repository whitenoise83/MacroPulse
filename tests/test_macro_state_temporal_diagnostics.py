from __future__ import annotations

import json
from datetime import date

import pandas as pd

from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.temporal_diagnostics import (
    TEMPORAL_POLICIES,
    apply_temporal_policy,
    decision_metrics,
    run_temporal_policy_diagnostics,
    transition_events,
)

REGIMES = [
    "hard_landing_risk", "stagflation_risk", "overheating",
    "disinflationary_expansion", "balanced_expansion", "reflation",
    "demand_slowdown", "mixed_transition",
]


def _probabilities(primary: str, probability: float = 0.55) -> str:
    remainder = (1.0 - probability) / (len(REGIMES) - 1)
    return json.dumps({
        regime: probability if regime == primary else remainder
        for regime in REGIMES
    }, sort_keys=True)


def _monthly() -> pd.DataFrame:
    dates = pd.date_range("2022-01-31", periods=18, freq="ME").date
    actual = (
        ["balanced_expansion"] * 4
        + ["reflation"] * 5
        + ["overheating"] * 4
        + ["mixed_transition"] * 5
    )
    forecast = (
        ["balanced_expansion"] * 3
        + ["reflation"] * 6
        + ["overheating"] * 3
        + ["mixed_transition"] * 6
    )
    rows = []
    for index, (state_date, actual_regime, forecast_regime) in enumerate(
        zip(dates, actual, forecast)
    ):
        fg = 0.5 + 0.05 * index
        ag = fg + (0.1 if index % 2 else -0.1)
        fi = 0.2 + 0.04 * index
        ai = fi + 0.05
        fl = 0.4 - 0.02 * index
        al = fl - 0.05
        rows.append({
            "candidate_id": "core__independent_normal",
            "core_candidate_id": "core",
            "uncertainty_id": "independent_normal",
            "state_date": state_date,
            "forecast_growth": fg,
            "forecast_inflation": fi,
            "forecast_labour": fl,
            "actual_growth": ag,
            "actual_inflation": ai,
            "actual_labour": al,
            "growth_error": fg - ag,
            "inflation_error": fi - ai,
            "labour_error": fl - al,
            "forecast_regime": forecast_regime,
            "actual_regime": actual_regime,
            "forecast_family": "test",
            "actual_family": "test",
            "top_regime": forecast_regime,
            "top_probability": 0.55,
            "probabilities_json": _probabilities(forecast_regime),
        })
    return pd.DataFrame(rows)


def _config() -> dict:
    return {
        "temporal_diagnostics": {
            "score_deadzone": 0.25,
            "transition_matching_window_months": 2,
            "minimum_regimes_per_fold": 2,
            "maximum_regime_share": 0.85,
            "random_seed": 13032,
            "bootstrap_repetitions": 50,
            "bootstrap_block_months": 2,
            "bootstrap_confidence": 0.90,
            "policies": {
                "raw_monthly": {"method": "raw_monthly"},
                "hysteresis_thresholds": {
                    "minimum_top_probability": 0.60,
                    "minimum_probability_advantage": 0.10,
                },
                "one_month_confirmation": {"consecutive_months_required": 2},
                "persistence_prior": {"persistence_weight": 0.35},
            },
            "fold_score_weights": {
                "exact_regime_accuracy": 0.25,
                "family_accuracy": 0.15,
                "stable_month_accuracy": 0.10,
                "transition_f1": 0.20,
                "baseline_margin": 0.25,
                "false_transition_rate": 0.05,
            },
            "stability_score_weights": {
                "mean_fold_score": 0.30,
                "median_fold_score": 0.20,
                "rank_stability": 0.15,
                "baseline_dominance_rate": 0.25,
                "mean_transition_f1": 0.10,
            },
            "governance": {
                "minimum_baseline_dominance_rate": 0.60,
                "minimum_family_accuracy": 0.60,
                "minimum_transition_recall": 0.50,
                "maximum_false_transition_rate": 0.50,
                "maximum_regime_collapse_fold_rate": 0.40,
                "minimum_bootstrap_margin_lower": 0.00,
            },
        }
    }


def test_temporal_policy_catalog_is_fixed() -> None:
    assert TEMPORAL_POLICIES == (
        "raw_monthly", "hysteresis_thresholds",
        "one_month_confirmation", "persistence_prior",
    )


def test_one_month_confirmation_delays_switch() -> None:
    frame = apply_temporal_policy(_monthly(), "one_month_confirmation", _config())
    assert frame.loc[3, "raw_regime"] == "reflation"
    assert frame.loc[3, "decision_regime"] == "balanced_expansion"
    assert frame.loc[4, "decision_regime"] == "reflation"


def test_hysteresis_holds_weak_switch() -> None:
    frame = apply_temporal_policy(_monthly(), "hysteresis_thresholds", _config())
    assert frame.loc[3, "decision_regime"] == "balanced_expansion"


def test_persistence_prior_probabilities_sum_to_one() -> None:
    frame = apply_temporal_policy(_monthly(), "persistence_prior", _config())
    values = json.loads(frame.loc[5, "decision_probabilities_json"])
    assert abs(sum(values.values()) - 1.0) < 1e-12


def test_transition_events_match_with_window() -> None:
    frame = apply_temporal_policy(_monthly(), "raw_monthly", _config())
    events = transition_events(frame, frame["state_date"], 2)
    actual = events.loc[events["event_type"] == "actual_transition"]
    assert len(actual) == 3
    assert int(actual["matched"].sum()) >= 2


def test_decision_metrics_include_baseline_and_transitions() -> None:
    frame = apply_temporal_policy(_monthly(), "raw_monthly", _config())
    metrics = decision_metrics(frame, frame["state_date"], _config())
    assert 0.0 <= metrics["exact_regime_accuracy"] <= 1.0
    assert 0.0 <= metrics["transition_f1"] <= 1.0
    assert metrics["actual_transition_count"] == 3
    assert "baseline_margin" in metrics


def test_rolling_diagnostics_rank_four_policies() -> None:
    monthly = _monthly()
    dates = tuple(monthly["state_date"])
    plan = RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:6], dates[6:12]),
            RollingFold("fold_02", dates[:9], dates[9:15]),
        ),
        selection_dates=dates[:15],
        audit_dates=dates[15:],
    )
    result = run_temporal_policy_diagnostics(monthly, plan, _config())
    assert len(result["policy_stability"]) == 4
    assert len(result["fold_metrics"]) == 8

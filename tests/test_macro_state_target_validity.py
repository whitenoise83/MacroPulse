from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from macropulse.macro_state.target_validity import (
    audit_plan,
    economic_separation_audit,
    forecast_sign_rule,
    label_stability_audit,
    lineage_audit,
    threshold_sensitivity_summary,
)
from macropulse.macro_state.tournament import REGIME_FAMILY, classify_regime_with_thresholds
from macropulse.macro_state.versioning import load_macro_state_governance


def _row(growth: float, inflation: float, labour: float) -> pd.DataFrame:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    regime = classify_regime_with_thresholds(growth, inflation, labour, thresholds)
    return pd.DataFrame(
        [
            {
                "state_date": date(2024, 1, 31),
                "actual_growth": growth,
                "actual_inflation": inflation,
                "actual_labour": labour,
                "actual_regime": regime,
                "actual_family": REGIME_FAMILY[regime],
            }
        ]
    )


def test_audit_plan_is_prespecified() -> None:
    config = load_macro_state_governance()
    plan = audit_plan(config)
    assert plan.perturbation_epsilons == (0.05, 0.10, 0.25)
    assert plan.threshold_ids == ("sensitive", "baseline", "conservative")
    assert plan.economic_horizons == (1, 3, 6)


def test_label_far_from_boundary_is_more_stable() -> None:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    stable = label_stability_audit(_row(1.8, -1.8, 1.8), thresholds, config)
    fragile = label_stability_audit(_row(0.50, 0.50, 0.25), thresholds, config)
    assert stable.iloc[0]["regime_agreement_e0p1"] > fragile.iloc[0]["regime_agreement_e0p1"]
    assert stable.iloc[0]["regime_boundary_distance_linf"] >= fragile.iloc[0]["regime_boundary_distance_linf"]


def test_threshold_summary_contains_pairwise_agreements_and_occupancy() -> None:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    monthly = pd.concat(
        [_row(1.0, -1.0, 1.0), _row(-1.0, 1.0, -1.0)], ignore_index=True
    )
    monthly.loc[1, "state_date"] = date(2024, 2, 29)
    stability = label_stability_audit(monthly, thresholds, config)
    summary = threshold_sensitivity_summary(stability, config)
    assert (summary["comparison_type"] == "pairwise_agreement").sum() == 3
    assert (summary["comparison_type"] == "occupancy").sum() == 24


def test_lineage_audit_separates_forecast_lookahead_from_actual_vintage() -> None:
    inputs = pd.DataFrame(
        [
            {
                "state_date": date(2024, 1, 31),
                "source_target": "CPIAUCSL",
                "target_period": "2024-01",
                "information_cutoff": date(2024, 1, 25),
                "data_as_of": date(2024, 1, 25),
                "max_observation_date": date(2023, 12, 31),
                "actual_release_date": date(2024, 2, 13),
                "target_leakage": False,
            }
        ]
    )
    result = lineage_audit(inputs).iloc[0]
    assert result["information_cutoff_after_state"] == 0
    assert result["target_leakage_rows"] == 0
    assert bool(result["actual_revision_vintage_recorded"]) is False
    assert result["evaluation_target_mode"] == "ex_post_backtest_actual"


def test_sign_rule_maps_clear_macro_states() -> None:
    assert forecast_sign_rule(-1.0, -0.5, -1.0, 0.1) == "hard_landing_risk"
    assert forecast_sign_rule(-1.0, 1.0, -0.2, 0.1) == "stagflation_risk"
    assert forecast_sign_rule(1.0, 1.0, 1.0, 0.1) == "overheating"
    assert forecast_sign_rule(1.0, -1.0, 0.5, 0.1) == "disinflationary_expansion"


def test_economic_separation_detects_distinct_future_groups() -> None:
    config = load_macro_state_governance()
    dates = pd.date_range("2020-01-31", periods=30, freq="ME").date
    rows = []
    for index, state_date in enumerate(dates):
        high = index < 15
        regime = "overheating" if high else "hard_landing_risk"
        value = 1.5 if high else -1.5
        rows.append(
            {
                "state_date": state_date,
                "actual_growth": value,
                "actual_inflation": value,
                "actual_labour": value,
                "actual_regime": regime,
                "actual_family": REGIME_FAMILY[regime],
            }
        )
    result = economic_separation_audit(pd.DataFrame(rows), config)
    subset = result.loc[
        (result["horizon_months"] == 1)
        & (result["dimension"] == "growth")
        & (result["target_level"] == "eight_state")
        & (result["outcome_type"] == "future_level")
    ]
    assert subset.iloc[0]["eta_squared"] > 0.70


def test_model_identity_is_v038() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.8"

from __future__ import annotations

import json
from datetime import date

import pandas as pd

from macropulse.macro_state.temporal_diagnostics import (
    TemporalSource,
    confusion_table,
    latest_temporal_source,
    per_regime_metrics,
    target_decomposition,
)


class FakeRepository:
    def query_df(self, query: str, params=None) -> pd.DataFrame:
        return pd.DataFrame([{
            "stability_id": "stability-1",
            "reconstruction_id": "reconstruction-1",
            "selected_candidate_id": "core__independent_normal",
            "selected_core_candidate_id": "core",
            "selected_uncertainty_id": "independent_normal",
            "selected_governance_pass": False,
        }])


def _frame() -> pd.DataFrame:
    probabilities = json.dumps({
        "hard_landing_risk": 0.05, "stagflation_risk": 0.05,
        "overheating": 0.05, "disinflationary_expansion": 0.05,
        "balanced_expansion": 0.55, "reflation": 0.10,
        "demand_slowdown": 0.05, "mixed_transition": 0.10,
    }, sort_keys=True)
    return pd.DataFrame([
        {
            "state_date": date(2026, 1, 31),
            "forecast_growth": 0.5, "forecast_inflation": 0.1,
            "forecast_labour": 0.4, "actual_growth": 0.4,
            "actual_inflation": 0.2, "actual_labour": 0.3,
            "forecast_regime": "balanced_expansion",
            "actual_regime": "balanced_expansion",
            "forecast_family": "benign_expansion",
            "actual_family": "benign_expansion",
            "decision_regime": "balanced_expansion",
            "top_regime": "balanced_expansion",
            "decision_probabilities_json": probabilities,
        },
        {
            "state_date": date(2026, 2, 28),
            "forecast_growth": 0.8, "forecast_inflation": 0.7,
            "forecast_labour": 0.5, "actual_growth": 0.7,
            "actual_inflation": 0.8, "actual_labour": 0.4,
            "forecast_regime": "reflation", "actual_regime": "reflation",
            "forecast_family": "inflationary_expansion",
            "actual_family": "inflationary_expansion",
            "decision_regime": "reflation",
            "top_regime": "reflation",
            "decision_probabilities_json": probabilities,
        },
    ])


def test_latest_source_resolves_lineage() -> None:
    assert latest_temporal_source(FakeRepository()) == TemporalSource(
        "stability-1", "reconstruction-1", "core__independent_normal",
        "core", "independent_normal", False,
    )


def test_target_decomposition_contains_dimensions_and_decisions() -> None:
    result = target_decomposition(_frame(), _frame()["state_date"])
    assert set(result["dimension"]) == {
        "growth", "inflation", "labour", "eight_regime_point_decision",
        "regime_family_point_decision", "probability_top1_decision",
    }


def test_per_regime_metrics_retains_all_regimes() -> None:
    result = per_regime_metrics(_frame(), _frame()["state_date"])
    assert len(result) == 8
    assert int(result["support"].sum()) == 2


def test_confusion_table_is_full_eight_by_eight() -> None:
    result = confusion_table(_frame(), _frame()["state_date"])
    assert len(result) == 64
    assert int(result["count"].sum()) == 2

from __future__ import annotations

from datetime import date
import json

import pandas as pd

from macropulse.macro_state.history_diagnostics import (
    effective_coverage_metrics,
    joint_regime_distribution,
    transition_statistics,
)


def _config() -> dict:
    return {
        "history": {
            "uncertainty_candidate": {
                "method": "deterministic_gaussian_copula",
                "draws": 2048,
                "seed": 12022,
                "marginal_coverage": 0.80,
                "probability_floor": 0.01,
                "correlation": [
                    [1.00, 0.20, 0.55],
                    [0.20, 1.00, 0.25],
                    [0.55, 0.25, 1.00],
                ],
            }
        }
    }


def test_effective_coverage_uses_common_window() -> None:
    states = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                ["2025-09-30", "2025-11-30"]
            ).date
        }
    )
    result = effective_coverage_metrics(states)
    assert result["effective_months_requested"] == 3
    assert result["gap_months"] == 1
    assert result["effective_coverage_ratio"] == 2 / 3


def test_joint_distribution_is_deterministic() -> None:
    kwargs = dict(
        state_date=date(2026, 3, 31),
        growth_score=1.0,
        inflation_score=1.0,
        labour_score=0.5,
        growth_lower=-1.0,
        growth_upper=2.0,
        inflation_lower=-0.5,
        inflation_upper=2.0,
        labour_lower=-1.0,
        labour_upper=2.0,
        config=_config(),
    )
    first = joint_regime_distribution(**kwargs)
    second = joint_regime_distribution(**kwargs)
    assert first == second
    probabilities = json.loads(first["probabilities_json"])
    assert abs(sum(probabilities.values()) - 1.0) < 1e-12
    assert 0.0 <= first["top_probability"] <= 1.0
    assert 0.0 <= first["normalized_entropy"] <= 1.0


def test_transition_counts_exclude_month_gaps() -> None:
    states = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                ["2026-01-31", "2026-02-28", "2026-04-30"]
            ).date,
            "primary_regime": [
                "reflation",
                "overheating",
                "reflation",
            ],
        }
    )
    result = transition_statistics(states, minimum_count=3)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["from_regime"] == "reflation"
    assert row["to_regime"] == "overheating"
    assert int(row["transition_count"]) == 1
    assert bool(row["meets_minimum_count"]) is False

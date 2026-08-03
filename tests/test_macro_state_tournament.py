from __future__ import annotations

from datetime import date
import json

import numpy as np
import pandas as pd

from macropulse.macro_state.tournament import (
    build_core_candidates,
    chronological_split,
    classify_regime_with_thresholds,
    rank_core_metrics,
    regime_probability_distribution,
    target_score,
)
from pathlib import Path
import yaml


def load_macro_state_governance() -> dict:
    root = Path(__file__).resolve().parents[1]
    return yaml.safe_load(
        (root / "config" / "macro_state_governance.yml").read_text(
            encoding="utf-8"
        )
    )


def test_core_candidate_grid_has_81_specifications() -> None:
    config = load_macro_state_governance()
    candidates = build_core_candidates(config)
    assert len(candidates) == 81
    assert len({item["candidate_id"] for item in candidates}) == 81


def test_chronological_split_preserves_sealed_holdout() -> None:
    dates = pd.date_range("2020-01-31", periods=73, freq="ME").date
    split = chronological_split(
        dates,
        training_months=36,
        validation_months=18,
        minimum_holdout_months=12,
    )
    assert len(split.training_dates) == 36
    assert len(split.validation_dates) == 18
    assert len(split.holdout_dates) == 19
    assert split.training_dates[-1] < split.validation_dates[0]
    assert split.validation_dates[-1] < split.holdout_dates[0]


def test_expanding_normalisation_does_not_use_future_actuals() -> None:
    config = load_macro_state_governance()
    periods = list(range(1, 25))
    history = pd.DataFrame(
        {
            "source_target": ["PAYEMS"] * 24,
            "target_period_ordinal": periods,
            "actual": np.linspace(50.0, 200.0, 24),
        }
    )
    kwargs = dict(
        value=125.0,
        target="PAYEMS",
        target_period_ordinal=25,
        normalization_id="expanding_robust_z",
        config=config,
    )
    before = target_score(actual_history=history, **kwargs)
    future = pd.concat(
        [
            history,
            pd.DataFrame(
                {
                    "source_target": ["PAYEMS"],
                    "target_period_ordinal": [26],
                    "actual": [10_000.0],
                }
            ),
        ],
        ignore_index=True,
    )
    after = target_score(actual_history=future, **kwargs)
    assert before == after


def test_threshold_candidates_change_regime_sensitivity() -> None:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]
    sensitive = classify_regime_with_thresholds(
        0.6, 0.6, 0.3, thresholds["sensitive"]
    )
    conservative = classify_regime_with_thresholds(
        0.6, 0.6, 0.3, thresholds["conservative"]
    )
    assert sensitive == "overheating"
    assert conservative != "overheating"


def test_core_ranking_rewards_accuracy_and_low_error() -> None:
    validation = pd.DataFrame(
        [
            {
                "candidate_id": "strong",
                "dimension_rmse": 0.4,
                "exact_regime_accuracy": 0.6,
                "family_accuracy": 0.8,
                "sign_accuracy": 0.8,
                "churn_gap": 0.05,
                "distribution_jsd": 0.02,
                "regime_collapse_penalty": 0.0,
            },
            {
                "candidate_id": "weak",
                "dimension_rmse": 1.4,
                "exact_regime_accuracy": 0.2,
                "family_accuracy": 0.3,
                "sign_accuracy": 0.4,
                "churn_gap": 0.4,
                "distribution_jsd": 0.3,
                "regime_collapse_penalty": 0.4,
            },
        ]
    )
    config = load_macro_state_governance()
    ranked = rank_core_metrics(
        validation,
        config["tournament"]["core_metric_weights"],
    )
    assert ranked.iloc[0]["candidate_id"] == "strong"
    assert int(ranked.iloc[0]["core_rank"]) == 1


def test_uncertainty_distribution_is_deterministic_and_sums_to_one() -> None:
    config = load_macro_state_governance()
    candidate = build_core_candidates(config)[0]
    monthly = pd.DataFrame(
        {
            "state_date": pd.to_datetime(
                ["2024-01-31", "2024-02-29"]
            ).date,
            "growth_error": [0.1, -0.2],
            "inflation_error": [0.2, 0.1],
            "labour_error": [-0.1, 0.2],
        }
    )
    row = pd.Series(
        {
            "state_date": date(2024, 2, 29),
            "forecast_growth": 0.8,
            "forecast_inflation": 0.9,
            "forecast_labour": 0.6,
            "growth_lower": -0.5,
            "growth_upper": 2.0,
            "inflation_lower": -0.2,
            "inflation_upper": 1.8,
            "labour_lower": -0.6,
            "labour_upper": 1.7,
            "actual_regime": "overheating",
        }
    )
    first = regime_probability_distribution(
        row,
        monthly=monthly,
        core_candidate=candidate,
        uncertainty_id="fixed_gaussian_copula",
        config=config,
    )
    second = regime_probability_distribution(
        row,
        monthly=monthly,
        core_candidate=candidate,
        uncertainty_id="fixed_gaussian_copula",
        config=config,
    )
    assert first == second
    probabilities = json.loads(first["probabilities_json"])
    assert abs(sum(probabilities.values()) - 1.0) < 1e-12
    assert set(probabilities) == {
        "hard_landing_risk",
        "stagflation_risk",
        "overheating",
        "disinflationary_expansion",
        "balanced_expansion",
        "reflation",
        "demand_slowdown",
        "mixed_transition",
    }


def test_model_identity_is_v034() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.4"
    assert config["tournament"]["top_core_candidates"] == 12

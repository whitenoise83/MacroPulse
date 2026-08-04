from __future__ import annotations

import json

import pandas as pd
import pytest

from macropulse.macro_state.top2_robustness import prepare_predictions


FAMILIES = [
    "adverse_supply",
    "benign_expansion",
    "contraction",
    "inflationary_expansion",
    "mixed",
]


def test_canonical_v036_json_schema_and_overlapping_folds() -> None:
    dates = pd.date_range("2022-08-31", periods=6, freq="ME")
    rows = []
    for index, date in enumerate(dates):
        actual = FAMILIES[index % len(FAMILIES)]
        actual_probabilities = {family: 0.0 for family in FAMILIES}
        actual_probabilities[actual] = 1.0
        for benchmark in ("source", "rolling_frequency"):
            predicted = {family: 0.05 for family in FAMILIES}
            predicted[actual if benchmark == "source" else FAMILIES[0]] = 0.80
            total = sum(predicted.values())
            predicted = {key: value / total for key, value in predicted.items()}
            rows.append(
                {
                    "state_date": date,
                    "benchmark_id": benchmark,
                    "actual_family": actual,
                    "actual_probabilities_json": json.dumps(actual_probabilities),
                    "predicted_family": max(predicted, key=predicted.get),
                    "predicted_probabilities_json": json.dumps(predicted),
                    "predicted_top_probability": max(predicted.values()),
                }
            )

    fold_rows = []
    for fold_id, start, end in (
        ("fold_01", dates[0], dates[3]),
        ("fold_02", dates[2], dates[5]),
    ):
        for benchmark in ("source", "rolling_frequency"):
            fold_rows.append(
                {
                    "fold_id": fold_id,
                    "evaluation_start": start,
                    "evaluation_end": end,
                    "benchmark_id": benchmark,
                    "observations": 4,
                }
            )

    prepared, families, columns = prepare_predictions(
        pd.DataFrame(rows),
        pd.DataFrame(fold_rows),
    )

    assert families == FAMILIES
    assert "predicted_top" not in families
    assert columns["actual_family"] == "actual_family"
    assert columns["fold"] == "fold_id"
    assert len(prepared) == 16
    assert prepared.groupby(["fold_id", "benchmark_id"]).size().eq(4).all()
    assert prepared[[f"prob__{family}" for family in FAMILIES]].sum(axis=1).eq(1).all()
    assert prepared[[f"target__{family}" for family in FAMILIES]].sum(axis=1).eq(1).all()


def test_fold_metrics_uses_positional_alignment_with_duplicate_indices() -> None:
    from macropulse.macro_state.top2_robustness import fold_metrics

    monthly = pd.DataFrame(
        {
            "fold_id": ["fold_01"] * 6,
            "actual_family": ["a", "a", "b", "b", "c", "c"],
            "source_predicted_family": ["a", "b", "b", "b", "c", "a"],
            "rolling_frequency_predicted_family": ["a", "a", "a", "b", "b", "c"],
            "source_top1_hit": [True, False, True, True, True, False],
            "rolling_frequency_top1_hit": [True, True, False, True, False, True],
            "source_top2_hit": [True, True, True, True, True, False],
            "rolling_frequency_top2_hit": [True] * 6,
            "source_actual_family_probability": [0.7, 0.2, 0.6, 0.8, 0.7, 0.1],
            "rolling_frequency_actual_family_probability": [0.6] * 6,
            "source_soft_brier": [0.4, 0.9, 0.3, 0.2, 0.4, 1.0],
            "rolling_frequency_soft_brier": [0.5] * 6,
            "source_brier_improvement": [0.1, -0.4, 0.2, 0.3, 0.1, -0.5],
            "source_soft_log_loss": [0.5, 1.5, 0.6, 0.3, 0.5, 2.0],
            "rolling_frequency_soft_log_loss": [0.8] * 6,
            "source_log_loss_improvement": [0.3, -0.7, 0.2, 0.5, 0.3, -1.2],
        },
        index=[0, 1, 2, 0, 1, 2],
    )

    result = fold_metrics(monthly)

    assert len(result) == 1
    assert result.loc[0, "source_family_balanced_accuracy"] == pytest.approx(
        (0.5 + 1.0 + 0.5) / 3.0
    )
    assert result.loc[0, "rolling_frequency_family_balanced_accuracy"] == pytest.approx(
        (1.0 + 0.5 + 0.5) / 3.0
    )



def test_rank_diagnostics_replaces_raw_predicted_family_column() -> None:
    from macropulse.macro_state.top2_robustness import (
        add_rank_diagnostics,
        build_monthly_attribution,
        AuditSettings,
    )

    dates = pd.date_range("2022-08-31", periods=3, freq="ME")
    rows = []
    for date, actual in zip(dates, FAMILIES[:3]):
        actual_probabilities = {family: 0.0 for family in FAMILIES}
        actual_probabilities[actual] = 1.0
        for benchmark in ("source", "rolling_frequency"):
            predicted = {family: 0.025 for family in FAMILIES}
            predicted[actual] = 0.90
            total = sum(predicted.values())
            predicted = {key: value / total for key, value in predicted.items()}
            rows.append(
                {
                    "state_date": date,
                    "benchmark_id": benchmark,
                    "actual_family": actual,
                    "actual_probabilities_json": json.dumps(actual_probabilities),
                    # This raw convenience field already exists in v0.3.6 and
                    # previously collided with the recomputed diagnostic field.
                    "predicted_family": max(predicted, key=predicted.get),
                    "predicted_probabilities_json": json.dumps(predicted),
                    "predicted_top_probability": max(predicted.values()),
                }
            )

    fold_rows = []
    for benchmark in ("source", "rolling_frequency"):
        fold_rows.append(
            {
                "fold_id": "fold_01",
                "evaluation_start": dates[0],
                "evaluation_end": dates[-1],
                "benchmark_id": benchmark,
                "observations": 3,
            }
        )

    prepared, families, columns = prepare_predictions(
        pd.DataFrame(rows),
        pd.DataFrame(fold_rows),
    )
    ranked = add_rank_diagnostics(prepared, families, columns)

    assert ranked.columns.tolist().count("predicted_family") == 1
    assert not ranked.columns.duplicated().any()

    monthly, _, _ = build_monthly_attribution(
        ranked,
        families,
        columns,
        AuditSettings(bootstrap_repetitions=20),
    )
    assert monthly.columns.tolist().count("source_predicted_family") == 1
    assert monthly.columns.tolist().count(
        "rolling_frequency_predicted_family"
    ) == 1
    assert monthly["source_predicted_family"].map(type).eq(str).all()



def test_soft_log_loss_uses_v036_probability_floor() -> None:
    import numpy as np
    from macropulse.macro_state.top2_robustness import _score

    frame = pd.DataFrame(
        {
            "prob__a": [0.0],
            "prob__b": [1.0],
            "target__a": [1.0],
            "target__b": [0.0],
        }
    )
    scored = _score(frame, ["a", "b"])
    assert scored.loc[0, "soft_log_loss"] == pytest.approx(-np.log(1e-12))


def test_governance_reconciles_log_loss_and_documents_dimension_unavailability(
    tmp_path,
) -> None:
    from types import SimpleNamespace
    from macropulse.macro_state.top2_robustness import (
        AuditSettings,
        governance_table,
    )

    monthly = pd.DataFrame(
        {
            "fold_id": ["fold_01"],
            "state_date": [pd.Timestamp("2024-01-31")],
            "source_top2_hit": [False],
            "miss_depth": ["rank_three_miss"],
            "dimension_attribution": [
                "unavailable_from_frozen_v036_evidence"
            ],
        }
    )
    comparison = pd.DataFrame(
        [
            {
                "source_soft_brier": 0.5,
                "rolling_frequency_soft_brier": 0.6,
                "source_soft_log_loss": 1.2,
                "rolling_frequency_soft_log_loss": 1.4,
                "source_top2_coverage": 0.5,
                "rolling_frequency_top2_coverage": 0.6,
            }
        ]
    )
    summary = pd.DataFrame(
        [
            {
                "benchmark_id": "source",
                "mean_soft_brier": 0.5,
                "mean_soft_log_loss": 1.2,
                "mean_top2_coverage": 0.5,
            },
            {
                "benchmark_id": "rolling_frequency",
                "mean_soft_brier": 0.6,
                "mean_soft_log_loss": 1.4,
                "mean_top2_coverage": 0.6,
            },
        ]
    )
    inherited = pd.DataFrame(
        [
            {"check_id": "fixed_horizon_target_locked", "passed": True},
            {
                "check_id": "latest_revised_substitution_prohibited",
                "passed": True,
            },
            {
                "check_id": "benchmark_availability_no_lookahead",
                "passed": True,
            },
            {"check_id": "prospective_shadow_isolation", "passed": True},
        ]
    )
    bundle = SimpleNamespace(
        predictions=tmp_path / "benchmark_predictions.csv"
    )
    flags = governance_table(
        bundle,
        monthly,
        comparison,
        summary,
        inherited,
        AuditSettings(),
    )
    by_id = flags.set_index("check_id")
    assert bool(by_id.loc["source_log_loss_reconciles_v036", "passed"])
    assert bool(by_id.loc["rolling_log_loss_reconciles_v036", "passed"])
    assert bool(
        by_id.loc[
            "dimension_attribution_unavailable_documented", "passed"
        ]
    )

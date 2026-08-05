from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from macropulse.data.repository import MacroRepository


FAMILIES = [
    "adverse_supply",
    "benign_expansion",
    "contraction",
    "inflationary_expansion",
    "mixed",
]


def _frames(
    *,
    shadow_run_id: str = "shadow-2026-08",
    state_date: date = date(2026, 8, 31),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    created = pd.Timestamp("2026-08-31 12:05:00")
    cutoff = state_date
    probabilities = {
        "adverse_supply": 0.10,
        "benign_expansion": 0.20,
        "contraction": 0.10,
        "inflationary_expansion": 0.50,
        "mixed": 0.10,
    }
    probability_json = pd.Series([probabilities]).to_json(orient="records")
    probability_json = probability_json[1:-1]

    run_record = pd.DataFrame(
        [
            {
                "shadow_run_id": shadow_run_id,
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "run_timestamp": pd.Timestamp("2026-08-31 12:00:00"),
                "state_date": state_date,
                "information_cutoff": cutoff,
                "target_mode": "fixed_horizon_90d",
                "target_horizon_days": 90,
                "target_expected_available_date": date(2026, 11, 29),
                "source_candidate_id": (
                    "expanding_robust_z__policy__equal__sensitive__"
                    "independent_normal"
                ),
                "source_evidence_version": "0.3.6",
                "primary_comparator": "rolling_frequency",
                "source_macro_state_run_id": "macro-run-1",
                "gdp_run_id": "gdp-run-1",
                "inflation_run_id": "inflation-run-1",
                "labour_run_id": "labour-run-1",
                "config_hash": "a" * 64,
                "code_hash": "b" * 64,
                "git_commit": "test",
                "information_set_hash": "c" * 64,
                "source_bundle_hash": "d" * 64,
                "no_look_ahead_pass": True,
                "status": "predicted",
                "governance_json": "{}",
                "notes": None,
                "created_at": created,
            }
        ]
    )

    predictions = pd.DataFrame(
        [
            {
                "shadow_run_id": shadow_run_id,
                "model_version": "0.3.8",
                "state_date": state_date,
                "information_cutoff": cutoff,
                "prediction_timestamp": pd.Timestamp(
                    "2026-08-31 12:01:00"
                ),
                "benchmark_id": benchmark,
                "predicted_family": "inflationary_expansion",
                "predicted_probabilities_json": probability_json,
                "top1_family": "inflationary_expansion",
                "top2_family": "benign_expansion",
                "top3_family": "adverse_supply",
                "top1_probability": 0.50,
                "top2_probability": 0.20,
                "top3_probability": 0.10,
                "top1_top2_gap": 0.30,
                "entropy": 1.3592,
                "probability_sum": 1.0,
                "probability_vector_hash": (
                    "e" * 64 if benchmark == "source" else "f" * 64
                ),
                "no_look_ahead_pass": True,
                "created_at": created,
            }
            for benchmark in ("source", "rolling_frequency")
        ]
    )

    dimension_specs = [
        (
            "growth", 0.8, 0.4, 1.2, "Above-trend growth",
            "US_GDP_NOWCAST_1A", "gdp-run-1",
        ),
        (
            "inflation", 1.1, 0.7, 1.5, "Elevated inflation pressure",
            "US_INFLATION_NOWCAST_1B", "inflation-run-1",
        ),
        (
            "labour", 0.6, 0.2, 1.0, "Tight labour market",
            "US_LABOUR_NOWCAST_1C", "labour-run-1",
        ),
    ]
    dimensions = pd.DataFrame(
        [
            {
                "shadow_run_id": shadow_run_id,
                "model_version": "0.3.8",
                "state_date": state_date,
                "information_cutoff": cutoff,
                "dimension": dimension,
                "score": score,
                "lower_score": lower,
                "upper_score": upper,
                "label": label,
                "confidence": 80.0,
                "source_model_id": model_id,
                "source_model_version": "1.0.0",
                "source_run_id": source_run_id,
                "source_information_cutoff": cutoff,
                "source_data_as_of": cutoff,
                "source_hash": dimension[0] * 64,
                "no_look_ahead_pass": True,
                "created_at": created,
            }
            for (
                dimension, score, lower, upper, label, model_id, source_run_id
            ) in dimension_specs
        ]
    )
    return run_record, predictions, dimensions


def _outcomes(
    *,
    shadow_run_id: str = "shadow-2026-08",
    state_date: date = date(2026, 8, 31),
) -> pd.DataFrame:
    target = {
        "adverse_supply": 0.0,
        "benign_expansion": 0.0,
        "contraction": 0.0,
        "inflationary_expansion": 1.0,
        "mixed": 0.0,
    }
    target_json = pd.Series([target]).to_json(orient="records")[1:-1]
    created = pd.Timestamp("2026-11-29 12:05:00")
    return pd.DataFrame(
        [
            {
                "outcome_id": f"outcome-{benchmark}",
                "shadow_run_id": shadow_run_id,
                "model_version": "0.3.8",
                "state_date": state_date,
                "benchmark_id": benchmark,
                "resolved_at": pd.Timestamp("2026-11-29 12:00:00"),
                "target_mode": "fixed_horizon_90d",
                "target_horizon_days": 90,
                "target_available_date": date(2026, 11, 29),
                "target_vintage_id": "fixed-90d-2026-08",
                "actual_family": "inflationary_expansion",
                "actual_probabilities_json": target_json,
                "actual_confidence": 1.0,
                "actual_probability": 0.50,
                "brier_score": 0.32,
                "log_loss": 0.693147,
                "top1_hit": True,
                "top2_hit": True,
                "top3_hit": True,
                "previous_actual_family": "benign_expansion",
                "transition_flag": True,
                "target_hash": "1" * 64,
                "evaluation_hash": (
                    "2" * 64 if benchmark == "source" else "3" * 64
                ),
                "no_look_ahead_pass": True,
                "created_at": created,
            }
            for benchmark in ("source", "rolling_frequency")
        ]
    )


def _repository(tmp_path) -> MacroRepository:
    repository = MacroRepository(tmp_path / "shadow.duckdb")
    repository.initialise()
    return repository


def test_prediction_bundle_is_persisted_atomically(tmp_path) -> None:
    repository = _repository(tmp_path)
    run_record, predictions, dimensions = _frames()

    repository.save_macro_state_shadow_predictions(
        run_record, predictions, dimensions
    )

    assert len(repository.query_df("SELECT * FROM macro_state_shadow_runs")) == 1
    assert (
        len(repository.query_df("SELECT * FROM macro_state_shadow_predictions"))
        == 2
    )
    assert (
        len(repository.query_df("SELECT * FROM macro_state_shadow_dimensions"))
        == 3
    )
    assert repository.query_df(
        "SELECT * FROM macro_state_shadow_outcomes"
    ).empty


def test_duplicate_prediction_bundle_is_rejected_without_mutation(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    run_record, predictions, dimensions = _frames()
    repository.save_macro_state_shadow_predictions(
        run_record, predictions, dimensions
    )

    with pytest.raises(ValueError, match="append-only violation"):
        repository.save_macro_state_shadow_predictions(
            run_record, predictions, dimensions
        )

    counts = repository.query_df(
        """
        SELECT
            (SELECT COUNT(*) FROM macro_state_shadow_runs) AS runs,
            (SELECT COUNT(*) FROM macro_state_shadow_predictions)
                AS predictions,
            (SELECT COUNT(*) FROM macro_state_shadow_dimensions)
                AS dimensions
        """
    ).iloc[0]
    assert int(counts["runs"]) == 1
    assert int(counts["predictions"]) == 2
    assert int(counts["dimensions"]) == 3


def test_prediction_bundle_requires_frozen_benchmarks_and_dimensions(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    run_record, predictions, dimensions = _frames()
    predictions.loc[1, "benchmark_id"] = "soft_persistence"

    with pytest.raises(ValueError, match="source and rolling_frequency"):
        repository.save_macro_state_shadow_predictions(
            run_record, predictions, dimensions
        )

    assert repository.query_df(
        "SELECT * FROM macro_state_shadow_runs"
    ).empty


def test_prediction_bundle_rejects_look_ahead_dimension_cutoff(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    run_record, predictions, dimensions = _frames()
    dimensions.loc[
        dimensions["dimension"] == "inflation",
        "source_information_cutoff",
    ] = date(2026, 9, 1)

    with pytest.raises(ValueError, match="must not exceed"):
        repository.save_macro_state_shadow_predictions(
            run_record, predictions, dimensions
        )

    assert repository.query_df(
        "SELECT * FROM macro_state_shadow_runs"
    ).empty


def test_outcomes_require_target_availability_and_existing_predictions(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    outcomes = _outcomes()

    with pytest.raises(ValueError, match="before the shadow run exists"):
        repository.save_macro_state_shadow_outcomes(outcomes)

    run_record, predictions, dimensions = _frames()
    repository.save_macro_state_shadow_predictions(
        run_record, predictions, dimensions
    )
    outcomes["resolved_at"] = pd.Timestamp("2026-11-28 23:59:00")

    with pytest.raises(ValueError, match="must not precede"):
        repository.save_macro_state_shadow_outcomes(outcomes)

    assert repository.query_df(
        "SELECT * FROM macro_state_shadow_outcomes"
    ).empty


def test_outcomes_are_append_only(tmp_path) -> None:
    repository = _repository(tmp_path)
    run_record, predictions, dimensions = _frames()
    repository.save_macro_state_shadow_predictions(
        run_record, predictions, dimensions
    )
    outcomes = _outcomes()

    repository.save_macro_state_shadow_outcomes(outcomes)

    stored = repository.query_df(
        """
        SELECT benchmark_id, transition_flag, top1_hit
        FROM macro_state_shadow_outcomes
        ORDER BY benchmark_id
        """
    )
    assert list(stored["benchmark_id"]) == [
        "rolling_frequency",
        "source",
    ]
    assert stored["transition_flag"].all()
    assert stored["top1_hit"].all()

    with pytest.raises(ValueError, match="append-only violation"):
        repository.save_macro_state_shadow_outcomes(outcomes)

    assert (
        len(repository.query_df("SELECT * FROM macro_state_shadow_outcomes"))
        == 2
    )

def test_shadow_repository_methods_are_append_only() -> None:
    import inspect

    source = "\n".join(
        [
            inspect.getsource(
                MacroRepository.save_macro_state_shadow_predictions
            ),
            inspect.getsource(
                MacroRepository.save_macro_state_shadow_outcomes
            ),
        ]
    ).upper()
    for prohibited in (
        "UPDATE ",
        "DELETE ",
        "INSERT OR REPLACE",
        "UPSERT",
    ):
        assert prohibited not in source

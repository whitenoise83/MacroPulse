from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

duckdb = pytest.importorskip("duckdb")

from macropulse.data.repository import MacroRepository


def _require_working_duckdb() -> None:
    connection = duckdb.connect(":memory:")
    if connection is None:
        pytest.skip("DuckDB runtime is stubbed in the build environment.")
    connection.close()


def test_tournament_persistence_schema(tmp_path) -> None:
    _require_working_duckdb()
    repository = MacroRepository(tmp_path / "tournament.duckdb")
    repository.initialise()
    created = pd.Timestamp("2026-08-02 12:30:00")
    tournament_id = "tournament-test"
    run = pd.DataFrame(
        [
            {
                "tournament_id": tournament_id,
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.0",
                "reconstruction_id": "reconstruction-test",
                "created_at": created,
                "status": "success",
                "training_start": date(2020, 2, 29),
                "training_end": date(2023, 1, 31),
                "validation_start": date(2023, 2, 28),
                "validation_end": date(2024, 7, 31),
                "holdout_start": date(2024, 8, 31),
                "holdout_end": date(2026, 3, 31),
                "training_months": 36,
                "validation_months": 18,
                "holdout_months": 19,
                "core_candidates": 81,
                "uncertainty_candidates": 36,
                "selected_candidate_id": "winner__fixed_gaussian_copula",
                "selected_core_candidate_id": "winner",
                "selected_validation_score": 88.0,
                "selected_holdout_rank": 2,
                "config_hash": "a" * 64,
                "code_hash": "b" * 64,
                "git_commit": "test",
                "baseline_metrics_json": "{}",
                "metrics_json": "{}",
                "report_path": "reports/test.md",
                "notes": "test",
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "tournament_id": tournament_id,
                "candidate_id": "winner__fixed_gaussian_copula",
                "candidate_type": "uncertainty",
                "core_candidate_id": "winner",
                "normalization_id": "target_centered",
                "inflation_weights_id": "policy",
                "labour_weights_id": "hard_data",
                "threshold_id": "baseline",
                "uncertainty_id": "fixed_gaussian_copula",
                "selected": True,
                "validation_rank": 1,
                "holdout_rank": 2,
                "validation_score": 88.0,
                "holdout_score": 76.0,
                "config_json": "{}",
                "created_at": created,
            }
        ]
    )
    metrics = pd.DataFrame(
        [
            {
                "tournament_id": tournament_id,
                "candidate_id": "winner__fixed_gaussian_copula",
                "split": "validation",
                "months": 18,
                "dimension_rmse": 0.8,
                "dimension_mae": 0.6,
                "exact_regime_accuracy": 0.5,
                "family_accuracy": 0.7,
                "sign_accuracy": 0.8,
                "forecast_churn": 0.4,
                "actual_churn": 0.5,
                "churn_gap": 0.1,
                "distribution_jsd": 0.05,
                "forecast_regime_entropy": 0.7,
                "actual_regime_entropy": 0.7,
                "regime_collapse_penalty": 0.0,
                "forecast_regime_count": 5,
                "actual_regime_count": 5,
                "brier_score": 0.7,
                "log_loss": 1.2,
                "coverage_80": 0.83,
                "coverage_gap": 0.03,
                "mean_top_probability": 0.4,
                "mean_effective_regimes": 4.0,
                "top1_accuracy": 0.5,
                "core_score": 85.0,
                "uncertainty_score": 95.0,
                "final_score": 88.0,
                "created_at": created,
            }
        ]
    )
    monthly = pd.DataFrame(
        [
            {
                "tournament_id": tournament_id,
                "candidate_id": "winner__fixed_gaussian_copula",
                "core_candidate_id": "winner",
                "uncertainty_id": "fixed_gaussian_copula",
                "state_date": date(2024, 7, 31),
                "split": "validation",
                "forecast_growth": 0.5,
                "forecast_inflation": 0.6,
                "forecast_labour": 0.4,
                "actual_growth": 0.4,
                "actual_inflation": 0.5,
                "actual_labour": 0.3,
                "growth_lower": -0.5,
                "growth_upper": 1.5,
                "inflation_lower": -0.4,
                "inflation_upper": 1.6,
                "labour_lower": -0.6,
                "labour_upper": 1.4,
                "forecast_regime": "reflation",
                "actual_regime": "reflation",
                "top_regime": "reflation",
                "top_probability": 0.4,
                "actual_regime_probability": 0.4,
                "brier_score": 0.7,
                "log_loss": 0.916,
                "coverage_80": True,
                "effective_regimes": 4.0,
                "probabilities_json": "{}",
                "created_at": created,
            }
        ]
    )
    repository.save_macro_state_tournament(
        run_record=run,
        candidates=candidates,
        metrics=metrics,
        monthly=monthly,
    )
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_tournament_runs"
    ).iloc[0]["n"] == 1
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_tournament_candidates"
    ).iloc[0]["n"] == 1
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_tournament_metrics"
    ).iloc[0]["n"] == 1
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_tournament_monthly"
    ).iloc[0]["n"] == 1

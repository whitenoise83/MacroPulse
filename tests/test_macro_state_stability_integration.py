from __future__ import annotations

import pandas as pd
import pytest
import duckdb

from macropulse.data.repository import MacroRepository


def _require_working_duckdb() -> None:
    connection = duckdb.connect(":memory:")
    if connection is None:
        pytest.skip("DuckDB runtime is unavailable.")
    connection.close()


def test_stability_tables_persist(tmp_path) -> None:
    _require_working_duckdb()
    repository = MacroRepository(tmp_path / "stability.duckdb")
    repository.initialise()
    created = pd.Timestamp("2026-08-03 10:30:00")
    stability_id = "stability-test"
    run = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.1",
                "reconstruction_id": "history-test",
                "source_tournament_id": "tournament-test",
                "created_at": created,
                "status": "success",
                "fold_count": 1,
                "selection_start": pd.Timestamp("2020-02-29").date(),
                "selection_end": pd.Timestamp("2024-07-31").date(),
                "selection_months": 54,
                "audit_start": pd.Timestamp("2024-08-31").date(),
                "audit_end": pd.Timestamp("2026-03-31").date(),
                "audit_months": 19,
                "core_candidates": 81,
                "final_candidates": 36,
                "selected_candidate_id": "final-a",
                "selected_core_candidate_id": "core-a",
                "selected_uncertainty_id": "independent_normal",
                "selected_stability_score": 75.0,
                "selected_stability_rank": 1,
                "selected_governance_pass": False,
                "selected_audit_rank": 10,
                "config_hash": "a" * 64,
                "code_hash": "b" * 64,
                "git_commit": "test",
                "warnings_json": "[]",
                "report_path": "report.md",
                "notes": "test",
            }
        ]
    )
    folds = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "fold_id": "fold_01",
                "training_start": pd.Timestamp("2020-02-29").date(),
                "training_end": pd.Timestamp("2022-07-31").date(),
                "training_months": 30,
                "evaluation_start": pd.Timestamp("2022-08-31").date(),
                "evaluation_end": pd.Timestamp("2023-01-31").date(),
                "evaluation_months": 6,
                "created_at": created,
            }
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "candidate_id": "final-a",
                "candidate_type": "final",
                "core_candidate_id": "core-a",
                "uncertainty_id": "independent_normal",
                "selected": True,
                "governance_pass": False,
                "stability_rank": 1,
                "stability_score": 75.0,
                "folds": 1,
                "mean_fold_score": 75.0,
                "median_fold_score": 75.0,
                "mean_fold_rank": 1.0,
                "median_fold_rank": 1.0,
                "rank_std": 0.0,
                "best_fold_rank": 1,
                "worst_fold_rank": 1,
                "fold_win_rate": 1.0,
                "leading_third_rate": 1.0,
                "catastrophic_fold_count": 0,
                "baseline_dominance_rate": 0.0,
                "mean_baseline_margin": -0.1,
                "average_regret": 0.0,
                "regime_collapse_fold_rate": 0.0,
                "uncertainty_method_win_rate": 1.0,
                "proper_score_dominance_rate": 1.0,
                "bootstrap_margin_mean": -0.1,
                "bootstrap_margin_lower": -0.2,
                "bootstrap_margin_upper": 0.0,
                "audit_final_score": 50.0,
                "audit_final_rank": 10,
                "audit_exact_regime_accuracy": 0.4,
                "audit_brier_score": 0.8,
                "audit_log_loss": 1.5,
                "audit_coverage_80": 0.8,
                "audit_top1_accuracy": 0.4,
                "audit_baseline_margin": -0.2,
                "metrics_json": "{}",
                "created_at": created,
            }
        ]
    )
    fold_metrics = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "fold_id": "fold_01",
                "candidate_id": "final-a",
                "candidate_type": "final",
                "core_candidate_id": "core-a",
                "uncertainty_id": "independent_normal",
                "evaluation_start": pd.Timestamp("2022-08-31").date(),
                "evaluation_end": pd.Timestamp("2023-01-31").date(),
                "evaluation_months": 6,
                "score": 75.0,
                "rank": 1,
                "core_score": 75.0,
                "uncertainty_score": 75.0,
                "dimension_rmse": 0.5,
                "exact_regime_accuracy": 0.5,
                "family_accuracy": 0.7,
                "sign_accuracy": 0.8,
                "regime_collapse_penalty": 0.0,
                "brier_score": 0.7,
                "log_loss": 1.4,
                "coverage_80": 0.8,
                "top1_accuracy": 0.5,
                "mode_accuracy": 0.3,
                "persistence_accuracy": 0.6,
                "strongest_baseline": "persistence",
                "strongest_baseline_accuracy": 0.6,
                "baseline_margin": -0.1,
                "beats_strongest_baseline": False,
                "uncertainty_method_rank": 1,
                "proper_score_improvement": 0.0,
                "proper_score_dominates": True,
                "created_at": created,
            }
        ]
    )
    audit = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "candidate_id": "final-a",
                "core_candidate_id": "core-a",
                "uncertainty_id": "independent_normal",
                "audit_final_score": 50.0,
                "audit_final_rank": 10,
                "audit_core_score": 50.0,
                "audit_core_rank": 10,
                "audit_uncertainty_score": 50.0,
                "audit_uncertainty_rank": 10,
                "audit_exact_regime_accuracy": 0.4,
                "audit_family_accuracy": 0.6,
                "audit_sign_accuracy": 0.7,
                "audit_dimension_rmse": 0.8,
                "audit_regime_collapse_penalty": 0.0,
                "audit_brier_score": 0.8,
                "audit_log_loss": 1.5,
                "audit_coverage_80": 0.8,
                "audit_top1_accuracy": 0.4,
                "audit_mean_effective_regimes": 4.0,
                "audit_baseline_accuracy": 0.6,
                "audit_baseline_margin": -0.2,
                "created_at": created,
            }
        ]
    )
    subperiods = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "candidate_id": "final-a",
                "subperiod_id": "recent",
                "start_date": pd.Timestamp("2025-01-31").date(),
                "end_date": pd.Timestamp("2026-03-31").date(),
                "months": 14,
                "dimension_rmse": 0.8,
                "exact_regime_accuracy": 0.4,
                "family_accuracy": 0.6,
                "sign_accuracy": 0.7,
                "regime_collapse_penalty": 0.0,
                "brier_score": 0.8,
                "log_loss": 1.5,
                "coverage_80": 0.8,
                "top1_accuracy": 0.4,
                "mean_effective_regimes": 4.0,
                "created_at": created,
            }
        ]
    )
    repository.save_macro_state_stability_tournament(
        run_record=run,
        folds=folds,
        candidates=candidates,
        fold_metrics=fold_metrics,
        audit_metrics=audit,
        subperiod_metrics=subperiods,
    )
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_stability_runs"
    ).iloc[0]["n"] == 1
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_stability_candidates"
    ).iloc[0]["n"] == 1
    assert repository.query_df(
        "SELECT COUNT(*) AS n FROM macro_state_stability_fold_metrics"
    ).iloc[0]["n"] == 1

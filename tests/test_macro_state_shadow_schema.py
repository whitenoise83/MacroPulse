from __future__ import annotations

from pathlib import Path

from macropulse.data.repository import MacroRepository


EXPECTED_TABLES = {
    "macro_state_shadow_runs",
    "macro_state_shadow_predictions",
    "macro_state_shadow_dimensions",
    "macro_state_shadow_outcomes",
}


def test_shadow_schema_initialises_all_tables(tmp_path: Path) -> None:
    repository = MacroRepository(tmp_path / "shadow_schema.duckdb")
    repository.initialise()

    tables = repository.query_df(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
          AND table_name LIKE 'macro_state_shadow_%'
        ORDER BY table_name
        """
    )
    assert set(tables["table_name"]) == EXPECTED_TABLES

    run_columns = repository.query_df(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = 'macro_state_shadow_runs'
        ORDER BY ordinal_position
        """
    )
    assert {
        "shadow_run_id",
        "model_version",
        "state_date",
        "information_cutoff",
        "target_expected_available_date",
        "information_set_hash",
        "source_bundle_hash",
        "no_look_ahead_pass",
    }.issubset(set(run_columns["column_name"]))

    outcome_columns = repository.query_df(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = 'macro_state_shadow_outcomes'
        ORDER BY ordinal_position
        """
    )
    assert {
        "outcome_id",
        "benchmark_id",
        "target_available_date",
        "actual_probability",
        "brier_score",
        "log_loss",
        "transition_flag",
        "evaluation_hash",
    }.issubset(set(outcome_columns["column_name"]))


def test_shadow_schema_has_append_only_unique_indexes(tmp_path: Path) -> None:
    repository = MacroRepository(tmp_path / "shadow_indexes.duckdb")
    repository.initialise()

    indexes = repository.query_df(
        """
        SELECT index_name, is_unique
        FROM duckdb_indexes()
        WHERE table_name LIKE 'macro_state_shadow_%'
        ORDER BY index_name
        """
    )
    unique_indexes = set(
        indexes.loc[indexes["is_unique"], "index_name"].astype(str)
    )
    assert {
        "idx_macro_state_shadow_run_month",
        "idx_macro_state_shadow_prediction_unique",
        "idx_macro_state_shadow_prediction_month",
        "idx_macro_state_shadow_dimension_unique",
        "idx_macro_state_shadow_outcome_unique",
    }.issubset(unique_indexes)

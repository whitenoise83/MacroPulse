from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import pytest

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.history_service import run_macro_state_history


def _require_working_duckdb() -> None:
    connection = duckdb.connect(":memory:")
    if connection is None:
        pytest.skip("DuckDB runtime is unavailable.")
    connection.close()


def _seed(repository: MacroRepository) -> None:
    created = pd.Timestamp("2026-08-01 12:00:00")
    with repository.connect() as con:
        con.execute(
            """
            INSERT INTO forecast_registry (
                run_id, model_id, model_version, config_hash, code_hash,
                git_commit, information_set_hash, information_cutoff,
                data_as_of, target_period, forecast_stage,
                champion_model, production_forecast,
                lower_80, upper_80, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gdp-hist",
                "US_GDP_NOWCAST_1A",
                "1.0.0",
                "a" * 64,
                "b" * 64,
                "test",
                "c" * 64,
                date(2026, 1, 31),
                date(2026, 1, 30),
                "2026Q1",
                "after_month_1",
                "Stable",
                2.4,
                0.4,
                4.4,
                "success",
                created,
            ],
        )

        for table, run_id, model_id in [
            ("inflation_live_runs", "inflation-hist", "US_INFLATION_NOWCAST_1B"),
            ("labour_live_runs", "labour-hist", "US_LABOUR_NOWCAST_1C"),
        ]:
            con.execute(
                f"""
                INSERT INTO {table} VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    model_id,
                    "1.0.0",
                    created,
                    date(2026, 1, 31),
                    date(2026, 1, 30),
                    "success",
                    "candidate",
                    "backtest",
                    "a" * 64,
                    "b" * 64,
                    "test",
                    "c" * 64,
                    "d" * 64,
                    "e" * 64,
                    "{}",
                    "test",
                ],
            )

        for target, name, point, lower, upper in [
            ("PCEPILFE", "Core PCE", 2.0, 1.0, 3.0),
            ("CPILFESL", "Core CPI", 2.3, 1.2, 3.4),
            ("PCEPI", "Headline PCE", 1.8, 0.5, 3.1),
            ("CPIAUCSL", "Headline CPI", 2.0, 0.7, 3.3),
        ]:
            con.execute(
                """
                INSERT INTO inflation_live_forecasts VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "inflation-hist",
                    target,
                    name,
                    "2026-01",
                    "month_end",
                    date(2026, 1, 31),
                    date(2026, 2, 15),
                    "Stable",
                    point,
                    lower,
                    upper,
                    (upper - lower) / 2,
                    "exp_weighted_q80",
                    48,
                    "2025-12",
                    "Shadow",
                    point,
                    "test",
                    48,
                    "2025-12",
                    created,
                ],
            )

        for target, name, unit, decimals, point, lower, upper in [
            ("PAYEMS", "Payroll", "thousands", 0, 150.0, 20.0, 280.0),
            ("UNRATE", "Unemployment", "percent", 1, 4.2, 3.9, 4.7),
            ("CES0500000003", "Wages", "annualised percent", 3, 3.4, 2.2, 4.6),
        ]:
            con.execute(
                """
                INSERT INTO labour_live_forecasts (
                    run_id, target_series, target_name, target_unit,
                    display_decimals, target_period, forecast_stage,
                    information_cutoff, estimated_release_date,
                    stable_model_name, stable_point_forecast, lower_80,
                    upper_80, interval_half_width, interval_method,
                    interval_prior_errors, interval_cutoff_period,
                    shadow_model_name, shadow_point_forecast,
                    shadow_selection_reason, shadow_prior_errors,
                    latest_observed_period, created_at
                ) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "labour-hist",
                    target,
                    name,
                    unit,
                    decimals,
                    "2026-01",
                    "month_end",
                    date(2026, 1, 31),
                    date(2026, 2, 7),
                    "Stable",
                    point,
                    lower,
                    upper,
                    (upper - lower) / 2,
                    "exp_weighted_q80",
                    48,
                    "2025-12",
                    "Shadow",
                    point,
                    "test",
                    48,
                    "2025-12",
                    created,
                ],
            )


def test_history_reconstruction_persists_and_passes_no_look_ahead(tmp_path) -> None:
    _require_working_duckdb()
    repository = MacroRepository(tmp_path / "history.duckdb")
    repository.initialise()
    _seed(repository)

    result = run_macro_state_history(
        repository=repository,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        source_mode="live_runs",
    )

    assert result["months_reconstructed"] == 1
    assert result["no_look_ahead_pass"] is True
    assert len(result["states"]) == 1
    assert len(result["inputs"]) == 8

    metadata = repository.query_df(
        "SELECT * FROM macro_state_history_runs"
    )
    assert len(metadata) == 1
    assert bool(metadata.iloc[0]["no_look_ahead_pass"]) is True

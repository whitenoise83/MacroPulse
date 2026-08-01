from __future__ import annotations

from datetime import date

import pandas as pd
import duckdb
import pytest

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.service import run_macro_state


def _require_working_duckdb() -> None:
    try:
        connection = duckdb.connect(":memory:")
    except Exception as exc:
        pytest.skip(f"DuckDB unavailable in build environment: {exc}")
    if connection is None:
        pytest.skip("DuckDB runtime is stubbed in the build environment.")
    connection.close()


def _register_sources(repository: MacroRepository) -> None:
    created = pd.Timestamp("2026-08-01 12:00:00")
    rows = [
        ("US_GDP_NOWCAST_1A", "1.0.0", "GDP", "production"),
        ("US_INFLATION_NOWCAST_1B", "1.0.0", "Inflation", "production"),
        ("US_LABOUR_NOWCAST_1C", "1.0.0", "Labour", "production"),
    ]
    with repository.connect() as con:
        for model_id, version, name, status in rows:
            con.execute(
                """
                INSERT INTO model_registry VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    model_id,
                    version,
                    name,
                    status,
                    "a" * 64,
                    "b" * 64,
                    "test",
                    created,
                    "test",
                ],
            )


def _seed_sources(repository: MacroRepository) -> None:
    created = pd.Timestamp("2026-08-01 12:00:00")
    with repository.connect() as con:
        con.execute(
            """
            INSERT INTO forecast_registry VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gdp-run",
                "US_GDP_NOWCAST_1A",
                "1.0.0",
                "a" * 64,
                "b" * 64,
                "test",
                "c" * 64,
                date(2026, 8, 1),
                date(2026, 7, 31),
                "2026Q3",
                "after_month_1",
                "Stable Stage Policy",
                2.2,
                0.4,
                4.0,
                "success",
                created,
            ],
        )
        for table, run_id, model_id in [
            ("inflation_live_runs", "inflation-run", "US_INFLATION_NOWCAST_1B"),
            ("labour_live_runs", "labour-run", "US_LABOUR_NOWCAST_1C"),
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
                    date(2026, 8, 1),
                    date(2026, 7, 31),
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

        inflation_rows = [
            ("PCEPILFE", "Core PCE", 2.2, 1.0, 3.4),
            ("CPILFESL", "Core CPI", 2.5, 1.2, 3.8),
            ("PCEPI", "Headline PCE", 2.0, 0.5, 3.5),
            ("CPIAUCSL", "Headline CPI", 2.3, 0.8, 3.8),
        ]
        for target, name, point, lower, upper in inflation_rows:
            con.execute(
                """
                INSERT INTO inflation_live_forecasts VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "inflation-run",
                    target,
                    name,
                    "2026-07",
                    "month_end",
                    date(2026, 8, 1),
                    date(2026, 8, 15),
                    "Stable",
                    point,
                    lower,
                    upper,
                    (upper - lower) / 2,
                    "exp_weighted_q80",
                    48,
                    "2026-06",
                    "Shadow",
                    point,
                    "test",
                    48,
                    "2026-06",
                    created,
                ],
            )

        labour_rows = [
            (
                "PAYEMS",
                "Nonfarm Payroll Change",
                "thousands of jobs",
                0,
                120.0,
                -20.0,
                260.0,
            ),
            (
                "UNRATE",
                "Unemployment Rate",
                "percent",
                1,
                4.4,
                4.0,
                4.9,
            ),
            (
                "CES0500000003",
                "Average Hourly Earnings Growth",
                "annualised percent",
                3,
                3.4,
                2.0,
                4.8,
            ),
        ]
        for target, name, unit, decimals, point, lower, upper in labour_rows:
            con.execute(
                """
                INSERT INTO labour_live_forecasts (
                    run_id, target_series, target_name, target_unit,
                    display_decimals, target_period, forecast_stage,
                    information_cutoff, estimated_release_date,
                    stable_model_name, stable_point_forecast, lower_80, upper_80,
                    interval_half_width, interval_method, interval_prior_errors,
                    interval_cutoff_period, shadow_model_name,
                    shadow_point_forecast, shadow_selection_reason,
                    shadow_prior_errors, latest_observed_period, created_at
                ) VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "labour-run",
                    target,
                    name,
                    unit,
                    decimals,
                    "2026-07",
                    "month_end",
                    date(2026, 8, 1),
                    date(2026, 8, 7),
                    "Stable",
                    point,
                    lower,
                    upper,
                    (upper - lower) / 2,
                    "exp_weighted_q80",
                    48,
                    "2026-06",
                    "Shadow",
                    point,
                    "test",
                    48,
                    "2026-06",
                    created,
                ],
            )


def test_unified_state_persists_complete_source_bundle(tmp_path) -> None:
    _require_working_duckdb()
    repository = MacroRepository(tmp_path / "macro_state.duckdb")
    repository.initialise()
    _register_sources(repository)
    _seed_sources(repository)

    result = run_macro_state(repository, as_of=date(2026, 8, 1))

    assert result["model_id"] == "US_MACRO_STATE_1D"
    assert len(result["inputs"]) == 8
    assert set(result["dimensions"]["dimension"]) == {
        "growth",
        "inflation",
        "labour",
    }
    assert len(result["source_bundle_hash"]) == 64
    assert len(result["state_hash"]) == 64

    runs = repository.query_df("SELECT * FROM macro_state_runs")
    assert len(runs) == 1
    assert runs.iloc[0]["status"] == "success"
    assert runs.iloc[0]["gdp_run_id"] == "gdp-run"
    assert runs.iloc[0]["inflation_run_id"] == "inflation-run"
    assert runs.iloc[0]["labour_run_id"] == "labour-run"

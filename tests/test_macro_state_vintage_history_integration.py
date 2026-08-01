from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd
import pytest

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.vintage_history import (
    reconstruct_production_vintage_history,
)


def _require_working_duckdb() -> None:
    connection = duckdb.connect(":memory:")
    if connection is None:
        pytest.skip("DuckDB runtime is unavailable.")
    connection.close()


def test_production_vintage_history_uses_approved_lineage(
    tmp_path,
    monkeypatch,
) -> None:
    _require_working_duckdb()
    repository = MacroRepository(tmp_path / "vintage_history.duckdb")
    repository.initialise()
    created = pd.Timestamp("2026-08-01 12:00:00")

    gdp_cfg = {
        "model": {"approval": {"validation_id": "gdp-validation"}},
        "production_policy": {
            "stable_stage_policy": {
                "early_quarter": "Dynamic Factor Model",
                "after_month_1": "Dynamic Factor Model",
                "after_month_2": "Bridge–DFM Ensemble",
                "quarter_end": "Rolling Bridge–DFM Ensemble",
                "pre_advance_release": "Dynamic Factor Model",
            }
        },
    }
    inflation_cfg = {
        "model": {
            "approval": {
                "candidate_validation_id": "inflation-validation"
            }
        },
        "policy_candidate": {
            "stable_map": {
                target: {
                    "month_open": "Stable",
                    "mid_month": "Stable",
                    "month_end": "Stable",
                    "pre_release": "Stable",
                }
                for target in (
                    "CPIAUCSL",
                    "CPILFESL",
                    "PCEPI",
                    "PCEPILFE",
                )
            }
        },
        "interval_candidate": {"method": "exp_weighted_q80"},
    }
    labour_cfg = {
        "model": {
            "approval": {
                "candidate_validation_id": "labour-validation"
            }
        },
        "policy_candidate": {
            "stable_map": {
                target: {
                    "month_open": "Stable",
                    "after_week_1": "Stable",
                    "after_week_2": "Stable",
                    "month_end": "Stable",
                    "pre_employment_report": "Stable",
                }
                for target in (
                    "PAYEMS",
                    "UNRATE",
                    "CES0500000003",
                )
            }
        },
        "interval_candidate": {"method": "exp_weighted_q80"},
    }

    monkeypatch.setattr(
        "macropulse.macro_state.vintage_history._governance_files",
        lambda: (gdp_cfg, inflation_cfg, labour_cfg),
    )

    with repository.connect() as con:
        con.execute(
            """
            INSERT INTO validation_runs VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gdp-validation",
                created,
                "US_GDP_NOWCAST_1A",
                "0.6.1",
                "gdp-backtest",
                None,
                "pass",
                27,
                27,
                None,
                "{}",
                "test",
            ],
        )
        con.execute(
            """
            INSERT INTO inflation_validation_runs VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "inflation-validation",
                "US_INFLATION_NOWCAST_1B",
                "0.6.0",
                "inflation-backtest",
                created,
                "pass",
                28,
                0,
                0,
                None,
                "{}",
                "test",
            ],
        )
        con.execute(
            """
            INSERT INTO labour_validation_runs VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "labour-validation",
                "labour-backtest",
                "US_LABOUR_NOWCAST_1C",
                "0.6.0",
                created,
                "pass",
                39,
                0,
                0,
                None,
                "{}",
                "test",
            ],
        )

        con.execute(
            """
            INSERT INTO stage_backtest_results (
                stage_backtest_id, forecast_stage, forecast_date,
                target_period, actual_release_date, days_to_release,
                model_name, point_forecast, actual, error, abs_error,
                squared_error, direction_correct, raw_lower_80,
                raw_upper_80, lower_80, upper_80, interval_width,
                interval_covered, interval_method, interval_history,
                interval_details_json, imputed_feature_count,
                information_set_hash, model_version, created_at
            ) VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gdp-backtest",
                "quarter_end",
                date(2026, 3, 31),
                "2026Q1",
                date(2026, 4, 30),
                30,
                "Rolling Bridge–DFM Ensemble",
                2.4,
                2.2,
                -0.2,
                0.2,
                0.04,
                True,
                0.4,
                4.4,
                0.4,
                4.4,
                4.0,
                True,
                "stage_specific",
                20,
                "{}",
                0,
                "gdp-hash",
                "0.6.1",
                created,
            ],
        )

        for target in ("CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"):
            con.execute(
                """
                INSERT INTO inflation_vintage_backtest_results VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "inflation-backtest",
                    target,
                    "month_end",
                    date(2026, 3, 31),
                    "2026-03",
                    date(2026, 4, 15),
                    15,
                    "Stable",
                    2.0,
                    2.1,
                    -0.1,
                    0.1,
                    0.01,
                    0.8,
                    3.2,
                    True,
                    0,
                    f"{target}-hash",
                    date(2026, 3, 30),
                    60,
                    False,
                    created,
                ],
            )

        labour_values = {
            "PAYEMS": (150.0, 20.0, 280.0),
            "UNRATE": (4.2, 3.9, 4.7),
            "CES0500000003": (3.4, 2.2, 4.6),
        }
        for target, (point, lower, upper) in labour_values.items():
            con.execute(
                """
                INSERT INTO labour_vintage_backtest_results VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "labour-backtest",
                    target,
                    target,
                    "test",
                    "month_end",
                    date(2026, 3, 31),
                    "2026-03",
                    date(2026, 4, 3),
                    3,
                    "Stable",
                    point,
                    point,
                    0.0,
                    0.0,
                    0.0,
                    True,
                    lower,
                    upper,
                    True,
                    60,
                    0,
                    f"{target}-hash",
                    False,
                    date(2026, 3, 30),
                    "normal",
                    created,
                ],
            )

    states, inputs, lineage = reconstruct_production_vintage_history(
        repository,
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert len(states) == 1
    assert len(inputs) == 8
    assert bool(states.iloc[0]["no_look_ahead_pass"]) is True
    assert lineage.gdp_backtest_id == "gdp-backtest"
    assert lineage.inflation_backtest_id == "inflation-backtest"
    assert lineage.labour_backtest_id == "labour-backtest"

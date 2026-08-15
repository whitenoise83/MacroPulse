from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from macropulse.bvar.origins import derive_origin_grid, validate_origin_grid


def snapshot_through(last_quarter: str) -> pd.DataFrame:
    last = pd.Period(last_quarter, freq="Q")
    quarters = pd.period_range("2023Q4", last, freq="Q")
    rows: list[dict] = []
    gdp_value = 100.0
    pce_value = 100.0

    for quarter in quarters:
        q_start = quarter.start_time
        months = pd.date_range(q_start, periods=3, freq="MS")
        rows.append(
            {
                "series_id": "GDPC1",
                "observation_date": q_start.date(),
                "value": gdp_value,
            }
        )
        gdp_value += 1.0

        for month in months:
            rows.append(
                {
                    "series_id": "PCEPILFE",
                    "observation_date": month.date(),
                    "value": pce_value,
                }
            )
            rows.append(
                {
                    "series_id": "UNRATE",
                    "observation_date": month.date(),
                    "value": 4.0,
                }
            )
            rows.append(
                {
                    "series_id": "FEDFUNDS",
                    "observation_date": month.date(),
                    "value": 5.25,
                }
            )
            pce_value += 0.2
    return pd.DataFrame(rows)


def test_one_origin_per_newly_complete_quarter() -> None:
    mapping = {
        date(2024, 5, 15): snapshot_through("2024Q1"),
        date(2024, 6, 15): snapshot_through("2024Q1"),
        date(2024, 8, 15): snapshot_through("2024Q2"),
        date(2024, 9, 15): snapshot_through("2024Q2"),
        date(2024, 11, 15): snapshot_through("2024Q3"),
    }
    grid = derive_origin_grid(mapping, mapping.__getitem__)
    assert grid["origin_quarter"].tolist() == [
        "2024Q1", "2024Q2", "2024Q3"
    ]
    assert grid["as_of_date"].tolist() == [
        date(2024, 5, 15),
        date(2024, 8, 15),
        date(2024, 11, 15),
    ]


def test_first_observed_state_is_left_censored_only() -> None:
    mapping = {
        date(2024, 5, 15): snapshot_through("2024Q1"),
        date(2024, 8, 15): snapshot_through("2024Q2"),
    }
    grid = derive_origin_grid(mapping, mapping.__getitem__)
    assert grid["left_censored"].tolist() == [True, False]
    assert grid["admissible_for_pseudo_real_time"].tolist() == [False, True]
    validate_origin_grid(grid)


def test_forecast_horizon_labels_are_quarter_offsets() -> None:
    mapping = {
        date(2024, 5, 15): snapshot_through("2024Q1"),
        date(2024, 8, 15): snapshot_through("2024Q2"),
    }
    row = derive_origin_grid(mapping, mapping.__getitem__).iloc[1]
    assert row["target_h1"] == "2024Q3"
    assert row["target_h2"] == "2024Q4"
    assert row["target_h4"] == "2025Q2"
    assert row["target_h8"] == "2026Q2"


def test_origin_identity_is_deterministic() -> None:
    mapping = {
        date(2024, 5, 15): snapshot_through("2024Q1"),
        date(2024, 8, 15): snapshot_through("2024Q2"),
    }
    first = derive_origin_grid(mapping, mapping.__getitem__)
    second = derive_origin_grid(mapping, mapping.__getitem__)
    assert first["origin_id"].tolist() == second["origin_id"].tolist()
    assert (
        first["source_snapshot_hash"].tolist()
        == second["source_snapshot_hash"].tolist()
    )


def test_decreasing_last_complete_quarter_fails_closed() -> None:
    mapping = {
        date(2024, 7, 31): snapshot_through("2024Q2"),
        date(2024, 8, 15): snapshot_through("2024Q1"),
    }
    with pytest.raises(ValueError, match="decreased"):
        derive_origin_grid(mapping, mapping.__getitem__)


def test_skipped_quarter_transition_fails_closed() -> None:
    mapping = {
        date(2024, 5, 15): snapshot_through("2024Q1"),
        date(2024, 11, 15): snapshot_through("2024Q3"),
    }
    with pytest.raises(ValueError, match="skipped"):
        derive_origin_grid(mapping, mapping.__getitem__)


def test_duplicate_cutoff_is_deduplicated() -> None:
    cutoff = date(2024, 5, 15)
    snapshot = snapshot_through("2024Q1")
    grid = derive_origin_grid([cutoff, cutoff], lambda _: snapshot)
    assert len(grid) == 1


def test_empty_cutoff_inventory_returns_empty_grid() -> None:
    grid = derive_origin_grid([], lambda _: pd.DataFrame())
    assert grid.empty

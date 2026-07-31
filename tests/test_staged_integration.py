from __future__ import annotations

import sys
import types
from datetime import date

import numpy as np
import pandas as pd

# The test exercises the staged orchestration with an in-memory repository. The
# production repository still uses DuckDB; a minimal import stub keeps this test
# independent of the local binary package availability.
if "duckdb" not in sys.modules:
    duckdb_stub = types.ModuleType("duckdb")
    duckdb_stub.DuckDBPyConnection = object
    duckdb_stub.connect = lambda *args, **kwargs: None
    sys.modules["duckdb"] = duckdb_stub

from macropulse.backtesting.staged import (  # noqa: E402
    StageBacktestConfig,
    run_staged_pseudo_realtime_backtest,
)


SERIES = ["GDPC1", "INDPRO", "PAYEMS", "RSAFS", "HOUST", "AWHMAN", "UNRATE", "CPIAUCSL", "FEDFUNDS"]


def _synthetic_source() -> dict[str, pd.DataFrame]:
    monthly_index = pd.date_range("1985-01-01", "2023-12-01", freq="MS")
    quarter_index = pd.date_range("1985-01-01", "2023-10-01", freq="QS")
    rng = np.random.default_rng(42)
    source: dict[str, pd.DataFrame] = {}

    gdp_growth = 0.6 + 0.15 * np.sin(np.arange(len(quarter_index)) / 4) + rng.normal(0, 0.03, len(quarter_index))
    gdp_level = 10000 * np.exp(np.cumsum(gdp_growth / 400))
    source["GDPC1"] = pd.DataFrame(
        {
            "observation_date": quarter_index,
            "value": gdp_level,
            "available_date": [
                (pd.Period(timestamp, freq="Q").end_time.normalize() + pd.Timedelta(days=28)).date()
                for timestamp in quarter_index
            ],
        }
    )

    base = np.arange(len(monthly_index), dtype=float)
    for position, series_id in enumerate(SERIES[1:], start=1):
        if series_id in {"UNRATE", "FEDFUNDS"}:
            values = 4.0 + 0.2 * np.sin(base / (8 + position)) + rng.normal(0, 0.02, len(base))
        else:
            values = (100 + position * 10) * np.exp(0.0015 * base + 0.01 * np.sin(base / (5 + position)))
            values *= np.exp(rng.normal(0, 0.002, len(base)))
        source[series_id] = pd.DataFrame(
            {
                "observation_date": monthly_index,
                "value": values,
                "available_date": [
                    (timestamp + pd.offsets.MonthEnd(0) + pd.Timedelta(days=15)).date()
                    for timestamp in monthly_index
                ],
            }
        )
    return source


class FakeClient:
    def __init__(self, source: dict[str, pd.DataFrame]) -> None:
        self.source = source

    def get_observations_as_of(self, series_id: str, observation_start: str, as_of_date: str) -> pd.DataFrame:
        cutoff = pd.Timestamp(as_of_date).date()
        frame = self.source[series_id]
        frame = frame.loc[
            (frame["observation_date"] >= pd.Timestamp(observation_start))
            & (frame["available_date"] <= cutoff)
        ].copy()
        frame["series_id"] = series_id
        frame["as_of_date"] = cutoff
        frame["retrieved_at"] = pd.Timestamp("2024-01-01")
        frame["source"] = "SYNTHETIC"
        return frame[["series_id", "as_of_date", "observation_date", "value", "retrieved_at", "source"]]


class FakeRepository:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, date], pd.DataFrame] = {}
        self.saved: dict[str, pd.DataFrame] = {}

    def initialise(self) -> None:
        return None

    def snapshot_is_cached(self, series_id: str, as_of_date: date) -> bool:
        return (series_id, as_of_date) in self.snapshots

    def replace_historical_snapshot(self, series_id: str, as_of_date: date, frame: pd.DataFrame) -> int:
        self.snapshots[(series_id, as_of_date)] = frame.copy()
        return len(frame)

    def historical_snapshot(self, as_of_date: date, series_ids: list[str] | None = None) -> pd.DataFrame:
        frames = []
        for series_id in series_ids or SERIES:
            frame = self.snapshots.get((series_id, as_of_date))
            if frame is not None:
                copy = frame.copy()
                copy["realtime_start"] = as_of_date
                copy["realtime_end"] = as_of_date
                frames.append(copy)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def initial_release_date(self, series_id: str, target_period: pd.Period) -> date | None:
        assert series_id == "GDPC1"
        return (target_period.end_time.normalize() + pd.Timedelta(days=28)).date()

    def save_stage_backtest_outputs(self, run_record: pd.DataFrame, results: pd.DataFrame, diagnostics: pd.DataFrame) -> None:
        self.saved["run"] = run_record.copy()
        self.saved["results"] = results.copy()
        self.saved["diagnostics"] = diagnostics.copy()


def test_staged_backtest_runs_multiple_cutoffs_without_lookahead() -> None:
    repository = FakeRepository()
    result = run_staged_pseudo_realtime_backtest(
        config=StageBacktestConfig(
            start_date="2022-01-01",
            end_date="2022-12-31",
            stages=("early_quarter", "quarter_end", "pre_advance_release"),
            include_dfm=False,
            request_pause_seconds=0,
            interval_min_history=2,
        ),
        repository=repository,
        client=FakeClient(_synthetic_source()),
    )
    assert result["status"] == "success"
    assert len(result["results"]) == 4 * 3 * 4  # Bridge, AR(1), stable policy, robust shadow policy
    assert set(result["results"]["forecast_stage"]) == {
        "early_quarter",
        "quarter_end",
        "pre_advance_release",
    }
    assert (pd.to_datetime(result["results"]["forecast_date"]) < pd.to_datetime(result["results"]["actual_release_date"])).all()
    assert result["results"]["information_set_hash"].str.len().eq(64).all()

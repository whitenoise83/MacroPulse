from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from macropulse.evaluation.ledger import (
    build_forecast_evaluation_ledger,
    collect_governed_forecasts,
    resolve_first_release_outcome,
    target_specs,
)


ROOT = Path(__file__).parents[1]


class FakeRepository:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def query_df(self, query: str, parameters=None) -> pd.DataFrame:
        self.queries.append(query)

        if "FROM forecast_registry" in query:
            return pd.DataFrame(
                [
                    {
                        "run_id": "gdp-run",
                        "model_id": "US_GDP_NOWCAST_1A",
                        "model_version": "1.0.0",
                        "information_cutoff": date(2025, 3, 31),
                        "data_as_of": date(2025, 3, 1),
                        "target_period": "2025Q1",
                        "forecast_stage": "late_quarter",
                        "forecast_model_name": "stable",
                        "forecast_value": 4.5,
                        "lower_80": 1.0,
                        "upper_80": 6.0,
                        "created_at": pd.Timestamp("2025-03-31"),
                    }
                ]
            )

        if "FROM inflation_live_runs AS r" in query:
            return pd.DataFrame(
                [
                    {
                        "run_id": "inflation-run",
                        "model_id": "US_INFLATION_NOWCAST_1B",
                        "model_version": "1.0.0",
                        "information_cutoff": date(2025, 1, 31),
                        "data_as_of": date(2025, 1, 30),
                        "target_series": "CPIAUCSL",
                        "target_name": "Headline CPI",
                        "target_period": "2025-01",
                        "forecast_stage": "late_month",
                        "forecast_model_name": "stable",
                        "forecast_value": 3.0,
                        "lower_80": 1.0,
                        "upper_80": 5.0,
                        "estimated_release_date": date(2025, 2, 12),
                        "created_at": pd.Timestamp("2025-01-31"),
                    }
                ]
            )

        if "FROM labour_live_runs AS r" in query:
            return pd.DataFrame(
                [
                    {
                        "run_id": "labour-run",
                        "model_id": "US_LABOUR_NOWCAST_1C",
                        "model_version": "1.0.0",
                        "information_cutoff": date(2025, 1, 31),
                        "data_as_of": date(2025, 1, 30),
                        "target_series": "UNRATE",
                        "target_name": "Unemployment Rate",
                        "target_period": "2025-01",
                        "forecast_stage": "late_month",
                        "forecast_model_name": "stable",
                        "forecast_value": 4.1,
                        "lower_80": 3.8,
                        "upper_80": 4.5,
                        "estimated_release_date": date(2025, 2, 7),
                        "created_at": pd.Timestamp("2025-01-31"),
                    }
                ]
            )

        if "FROM observations" in query and "vintage_type = 'initial'" in query:
            series_id = parameters[0]
            frames = {
                "GDPC1": pd.DataFrame(
                    {
                        "series_id": ["GDPC1", "GDPC1"],
                        "observation_date": ["2024-10-01", "2025-01-01"],
                        "realtime_start": ["2025-01-30", "2025-04-30"],
                        "realtime_end": ["9999-12-31", "9999-12-31"],
                        "value": [100.0, 101.0],
                        "vintage_type": ["initial", "initial"],
                        "retrieved_at": [
                            pd.Timestamp("2025-05-01"),
                            pd.Timestamp("2025-05-01"),
                        ],
                        "source": ["FRED", "FRED"],
                    }
                ),
                "CPIAUCSL": pd.DataFrame(
                    {
                        "series_id": ["CPIAUCSL", "CPIAUCSL"],
                        "observation_date": ["2024-12-01", "2025-01-01"],
                        "realtime_start": ["2025-01-15", "2025-02-12"],
                        "realtime_end": ["9999-12-31", "9999-12-31"],
                        "value": [100.0, 101.0],
                        "vintage_type": ["initial", "initial"],
                        "retrieved_at": [
                            pd.Timestamp("2025-02-13"),
                            pd.Timestamp("2025-02-13"),
                        ],
                        "source": ["FRED", "FRED"],
                    }
                ),
                "UNRATE": pd.DataFrame(
                    {
                        "series_id": ["UNRATE"],
                        "observation_date": ["2025-01-01"],
                        "realtime_start": ["2025-02-07"],
                        "realtime_end": ["9999-12-31"],
                        "value": [4.2],
                        "vintage_type": ["initial"],
                        "retrieved_at": [pd.Timestamp("2025-02-08")],
                        "source": ["FRED"],
                    }
                ),
            }
            return frames.get(series_id, pd.DataFrame()).copy()

        raise AssertionError(f"Unexpected query: {query}")


    def historical_snapshot(self, as_of_date, series_ids=None):
        series_id = series_ids[0]
        frames = {
            "GDPC1": pd.DataFrame(
                {
                    "series_id": ["GDPC1", "GDPC1"],
                    "observation_date": ["2024-10-01", "2025-01-01"],
                    "value": [100.2, 101.0],
                }
            ),
            "CPIAUCSL": pd.DataFrame(
                {
                    "series_id": ["CPIAUCSL", "CPIAUCSL"],
                    "observation_date": ["2024-12-01", "2025-01-01"],
                    "value": [100.2, 101.0],
                }
            ),
            "UNRATE": pd.DataFrame(
                {
                    "series_id": ["UNRATE"],
                    "observation_date": ["2025-01-01"],
                    "value": [4.2],
                }
            ),
        }
        return frames.get(series_id, pd.DataFrame()).copy()


def test_collect_governed_forecasts_contains_only_1a_1b_1c() -> None:
    repository = FakeRepository()
    forecasts = collect_governed_forecasts(
        repository,
        as_of=date(2025, 5, 1),
        project_root=ROOT,
    )
    assert set(forecasts["component"]) == {"1A", "1B", "1C"}
    assert set(forecasts["model_version"]) == {"1.0.0"}
    assert all("macro_state" not in query.lower() for query in repository.queries)


def test_build_ledger_resolves_exact_release_date_snapshots() -> None:
    repository = FakeRepository()
    ledger = build_forecast_evaluation_ledger(
        repository,
        as_of=date(2025, 5, 1),
        project_root=ROOT,
    )
    assert len(ledger) == 3
    assert set(ledger["evaluation_status"]) == {"resolved"}
    assert ledger["no_look_ahead_pass"].astype(bool).all()
    assert set(ledger["outcome_vintage"]) == {"first_release"}
    assert set(ledger["outcome_evidence_source"]) == {
        "historical_snapshots.release_date"
    }
    assert ledger["outcome_value"].notna().all()
    assert ledger["signed_error"].notna().all()
    # Initial-vintage observations identify the release date; the actual is
    # taken from the exact release-date historical snapshot.


def test_expected_future_release_remains_unresolved() -> None:
    repository = FakeRepository()

    class MissingCurrentVintage(FakeRepository):
        def query_df(self, query: str, parameters=None) -> pd.DataFrame:
            if "FROM observations" in query:
                return pd.DataFrame()
            return super().query_df(query, parameters)

    target = target_specs()[("1B", "CPIAUCSL")]
    resolution = resolve_first_release_outcome(
        MissingCurrentVintage(),
        target=target,
        target_period="2025-01",
        as_of=date(2025, 2, 10),
        expected_release_date=date(2025, 2, 12),
    )
    assert resolution.status == "unresolved_outcome_not_yet_available"
    assert resolution.value is None


def test_due_but_missing_initial_vintage_is_explicit() -> None:
    class MissingCurrentVintage(FakeRepository):
        def query_df(self, query: str, parameters=None) -> pd.DataFrame:
            if "FROM observations" in query:
                return pd.DataFrame()
            return super().query_df(query, parameters)

    target = target_specs()[("1B", "CPIAUCSL")]
    resolution = resolve_first_release_outcome(
        MissingCurrentVintage(),
        target=target,
        target_period="2025-01",
        as_of=date(2025, 2, 15),
        expected_release_date=date(2025, 2, 12),
    )
    assert resolution.status == "unresolved_initial_vintage_not_ingested"
    assert resolution.value is None


def test_future_target_period_fails_closed_without_guessing_release() -> None:
    class MissingCurrentVintage(FakeRepository):
        def query_df(self, query: str, parameters=None) -> pd.DataFrame:
            if "FROM observations" in query:
                return pd.DataFrame()
            return super().query_df(query, parameters)

    target = target_specs()[("1B", "CPIAUCSL")]
    resolution = resolve_first_release_outcome(
        MissingCurrentVintage(),
        target=target,
        target_period="2025-03",
        as_of=date(2025, 3, 10),
        expected_release_date=None,
    )
    assert resolution.status == "unresolved_outcome_not_yet_available"


def test_future_evaluation_date_fails_closed() -> None:
    with pytest.raises(ValueError, match="future"):
        collect_governed_forecasts(
            FakeRepository(),
            as_of=date(2999, 1, 1),
            project_root=ROOT,
        )


class MissingReleaseSnapshotRepository(FakeRepository):
    def historical_snapshot(self, as_of_date, series_ids=None):
        return pd.DataFrame()


def test_known_release_without_cached_snapshot_remains_unresolved() -> None:
    repository = MissingReleaseSnapshotRepository()
    target = target_specs()[("1B", "CPIAUCSL")]
    resolution = resolve_first_release_outcome(
        repository,
        target=target,
        target_period="2025-01",
        as_of=date(2025, 2, 15),
        expected_release_date=date(2025, 2, 12),
    )
    assert resolution.status == "unresolved_release_snapshot_not_cached"
    assert resolution.release_date == date(2025, 2, 12)
    assert resolution.value is None

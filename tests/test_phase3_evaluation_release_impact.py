from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from macropulse.evaluation.revisions import (
    associate_scheduled_releases,
    build_revision_table,
)


ROOT = Path(__file__).parents[1]


def revision_forecasts():
    return pd.DataFrame(
        [
            {
                "component": "1B",
                "run_id": "old",
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "1.0.0",
                "information_cutoff": date(2026, 8, 1),
                "data_as_of": date(2026, 8, 1),
                "target_series": "CPIAUCSL",
                "target_name": "Headline CPI",
                "target_period": "2026-07",
                "forecast_stage": "month_end",
                "forecast_model_name": "stable",
                "forecast_value": 1.0,
                "lower_80": 0.0,
                "upper_80": 2.0,
                "estimated_release_date": date(2026, 8, 12),
                "created_at": pd.Timestamp("2026-08-01 09:00"),
            },
            {
                "component": "1B",
                "run_id": "new",
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "1.0.0",
                "information_cutoff": date(2026, 8, 8),
                "data_as_of": date(2026, 8, 8),
                "target_series": "CPIAUCSL",
                "target_name": "Headline CPI",
                "target_period": "2026-07",
                "forecast_stage": "month_end",
                "forecast_model_name": "stable",
                "forecast_value": 1.2,
                "lower_80": 0.2,
                "upper_80": 2.2,
                "estimated_release_date": date(2026, 8, 12),
                "created_at": pd.Timestamp("2026-08-08 09:00"),
            },
        ]
    )


class FakeRepository:
    def query_df(self, query: str, parameters=None):
        if "FROM inflation_live_information_sets" in query:
            run_id = parameters[0]
            if run_id == "old":
                return pd.DataFrame(
                    {
                        "series_id": ["PAYEMS", "UNRATE"],
                        "latest_observation_date": [
                            date(2026, 6, 1),
                            date(2026, 6, 1),
                        ],
                    }
                )
            return pd.DataFrame(
                {
                    "series_id": ["PAYEMS", "UNRATE"],
                    "latest_observation_date": [
                        date(2026, 7, 1),
                        date(2026, 6, 1),
                    ],
                }
            )

        if "FROM release_calendar" in query:
            assert parameters[-2] == date(2026, 8, 1)
            assert parameters[-1] == date(2026, 8, 8)
            return pd.DataFrame(
                [
                    {
                        "series_id": "PAYEMS",
                        "release_id": "jobs",
                        "release_name": "Employment Situation",
                        "release_date": date(2026, 8, 7),
                    },
                    {
                        "series_id": "UNRATE",
                        "release_id": "jobs",
                        "release_name": "Employment Situation",
                        "release_date": date(2026, 8, 7),
                    },
                ]
            )
        raise AssertionError(f"Unexpected query: {query}")


def test_release_association_tracks_calendar_and_actual_source_advance() -> None:
    revisions = build_revision_table(revision_forecasts())
    enriched, events = associate_scheduled_releases(
        FakeRepository(),
        revisions,
        project_root=ROOT,
    )

    current = enriched.loc[
        enriched["comparison_status"] == "comparable_revision"
    ].iloc[0]
    assert current["associated_release_count"] == 2
    assert current["advanced_source_release_count"] == 1
    assert (
        current["release_association_state"]
        == "scheduled_releases_with_source_advance"
    )

    assert len(events) == 2
    payems = events.loc[events["series_id"] == "PAYEMS"].iloc[0]
    unrate = events.loc[events["series_id"] == "UNRATE"].iloc[0]
    assert bool(payems["information_set_advanced"]) is True
    assert bool(unrate["information_set_advanced"]) is False
    assert events["causality_claim"].eq(False).all()


class NoReleaseRepository(FakeRepository):
    def query_df(self, query: str, parameters=None):
        if "FROM release_calendar" in query:
            return pd.DataFrame(
                columns=[
                    "series_id",
                    "release_id",
                    "release_name",
                    "release_date",
                ]
            )
        return super().query_df(query, parameters)


def test_no_release_window_is_explicit() -> None:
    revisions = build_revision_table(revision_forecasts())
    enriched, events = associate_scheduled_releases(
        NoReleaseRepository(),
        revisions,
        project_root=ROOT,
    )
    current = enriched.loc[
        enriched["comparison_status"] == "comparable_revision"
    ].iloc[0]
    assert current["release_association_state"] == "no_scheduled_release"
    assert events.empty

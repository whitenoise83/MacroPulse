from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from macropulse.platform.status import collect_platform_status


class FakeRepository:
    def __init__(self, *, stale_inflation: bool = False) -> None:
        self.stale_inflation = stale_inflation
        self.calls: list[tuple[str, list]] = []

    def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
        params = parameters or []
        self.calls.append((query, params))
        compact = " ".join(query.split()).lower()

        if "from forecast_registry" in compact:
            return pd.DataFrame([{
                "run_id": "gdp-1",
                "model_id": "US_GDP_NOWCAST_1A",
                "model_version": "1.0.0",
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 7, 31),
                "target_period": "2026Q3",
                "forecast_stage": "after_month_1",
                "status": "success",
                "created_at": pd.Timestamp("2026-08-05"),
            }])

        if "from inflation_live_runs" in compact:
            return pd.DataFrame([{
                "run_id": "inflation-1",
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "1.0.0",
                "run_timestamp": pd.Timestamp("2026-08-05"),
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 8, 1),
                "status": "success",
            }])

        if "from labour_live_runs" in compact:
            return pd.DataFrame([{
                "run_id": "labour-1",
                "model_id": "US_LABOUR_NOWCAST_1C",
                "model_version": "1.0.0",
                "run_timestamp": pd.Timestamp("2026-08-05"),
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 8, 1),
                "status": "success",
            }])

        if "from macro_state_shadow_runs" in compact:
            return pd.DataFrame([{
                "shadow_run_id": "shadow-1",
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "run_timestamp": pd.Timestamp("2026-08-05"),
                "state_date": date(2026, 8, 31),
                "information_cutoff": date(2026, 8, 5),
                "target_expected_available_date": date(2026, 11, 29),
                "gdp_run_id": "gdp-1",
                "inflation_run_id": "inflation-1",
                "labour_run_id": "labour-1",
                "no_look_ahead_pass": True,
                "status": "predicted",
                "created_at": pd.Timestamp("2026-08-05"),
            }])

        if "from nowcast_information_sets" in compact:
            return pd.DataFrame([
                {"series_id": "GDP_SRC", "observation_date": date(2026, 7, 1)},
            ])

        if "from inflation_live_information_sets" in compact:
            return pd.DataFrame([
                {"series_id": "INF_SRC", "observation_date": date(2026, 7, 31)},
            ])

        if "from labour_live_information_sets" in compact:
            return pd.DataFrame([
                {"series_id": "LAB_SRC", "observation_date": date(2026, 8, 1)},
            ])

        if "from series_metadata" in compact:
            ids = [str(value) for value in params]
            frequencies = {
                "GDP_SRC": "M",
                "INF_SRC": "M",
                "LAB_SRC": "M",
            }
            return pd.DataFrame([
                {"series_id": value, "frequency": frequencies[value]}
                for value in ids
            ])

        if "from release_calendar" in compact:
            ids = {str(value) for value in params[:-2]}
            start = params[-2]
            end = params[-1]
            rows = []
            if self.stale_inflation and "INF_SRC" in ids:
                release = date(2026, 8, 6)
                if start < release <= end:
                    rows.append({
                        "series_id": "INF_SRC",
                        "release_id": 1,
                        "release_name": "Inflation source release",
                        "release_date": release,
                    })
            future = date(2026, 8, 12)
            if "LAB_SRC" in ids and start < future <= end:
                rows.append({
                    "series_id": "LAB_SRC",
                    "release_id": 2,
                    "release_name": "Labour source release",
                    "release_date": future,
                })
            return pd.DataFrame(
                rows,
                columns=["series_id", "release_id", "release_name", "release_date"],
            )

        if "count(*) as target_count from inflation_live_forecasts" in compact:
            return pd.DataFrame([{"target_count": 4}])

        if "count(*) as target_count from labour_live_forecasts" in compact:
            return pd.DataFrame([{"target_count": 3}])

        if "from macro_state_shadow_outcomes" in compact and "count(distinct state_date)" not in compact:
            return pd.DataFrame(columns=["benchmark_id"])

        if "count(distinct state_date) as complete_target_months" in compact:
            return pd.DataFrame([{"complete_target_months": 0}])

        raise AssertionError(f"Unexpected query: {compact}")


def write_boundary(root: Path) -> None:
    payload = {
        "phase": "II",
        "model_suite": {
            "1A": {"status": "production", "version": "1.0.0"},
            "1B": {"status": "production", "version": "1.0.0"},
            "1C": {"status": "production", "version": "1.0.0"},
            "1D": {
                "status": "development",
                "version": "0.3.8",
                "mode": "prospective_shadow",
                "promotion_authority": "none",
            },
        },
    }
    (root / "PHASE2_BOUNDARY.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_collect_status_is_read_only_and_ready(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    repository = FakeRepository()
    result = collect_platform_status(
        repository,
        as_of=date(2026, 8, 7),
        project_root=tmp_path,
    )

    components = result["components"].set_index("component")
    assert components.loc["1A", "freshness_state"] == "fresh"
    assert components.loc["1B", "freshness_state"] == "fresh"
    assert components.loc["1C", "freshness_state"] == "fresh"
    assert (
        components.loc["1D", "freshness_state"]
        == "frozen_prospective_observation"
    )

    readiness = result["readiness"].iloc[0]
    assert bool(readiness["production_sources_ready"]) is True
    assert bool(readiness["model1d_shadow_valid"]) is True
    assert bool(readiness["platform_ready_for_downstream"]) is True
    assert readiness["next_action"] == "no_model_action_required"

    assert not hasattr(repository, "save_model_outputs")
    assert all(call[0].lstrip().lower().startswith("select") for call in repository.calls)


def test_release_after_inflation_run_blocks_source_readiness(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    repository = FakeRepository(stale_inflation=True)
    result = collect_platform_status(
        repository,
        as_of=date(2026, 8, 7),
        project_root=tmp_path,
    )

    components = result["components"].set_index("component")
    assert components.loc["1B", "freshness_state"] == "stale"
    assert bool(components.loc["1B", "ready"]) is False

    readiness = result["readiness"].iloc[0]
    assert bool(readiness["production_sources_ready"]) is False
    assert bool(readiness["platform_ready_for_downstream"]) is False
    assert "1B" in readiness["blocking_components"]
    assert readiness["next_action"] == "refresh_or_repair_production_source_models"


def test_upcoming_release_window_is_reported(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    repository = FakeRepository()
    result = collect_platform_status(
        repository,
        as_of=date(2026, 8, 7),
        project_root=tmp_path,
    )
    upcoming = result["upcoming_releases"]
    assert len(upcoming) == 1
    assert upcoming.iloc[0]["series_id"] == "LAB_SRC"
    assert int(upcoming.iloc[0]["days_until_release"]) == 5

def test_newer_source_runs_do_not_invalidate_frozen_shadow(tmp_path: Path) -> None:
    write_boundary(tmp_path)

    class AdvancedSourceRepository(FakeRepository):
        def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
            frame = super().query_df(query, parameters)
            compact = " ".join(query.split()).lower()

            replacements = {
                "from forecast_registry": "gdp-2",
                "from inflation_live_runs": "inflation-2",
                "from labour_live_runs": "labour-2",
            }
            for marker, run_id in replacements.items():
                if marker in compact and not frame.empty:
                    frame = frame.copy()
                    frame.loc[:, "run_id"] = run_id
            return frame

    result = collect_platform_status(
        AdvancedSourceRepository(),
        as_of=date(2026, 8, 7),
        project_root=tmp_path,
    )

    component = result["components"].set_index("component").loc["1D"]
    detail = result["model1d"].iloc[0]

    assert component["freshness_state"] == "frozen_prospective_observation"
    assert bool(component["ready"]) is True
    assert bool(detail["source_runs_match_latest"]) is False
    assert bool(detail["source_run_advance_detected"]) is True

def test_source_run_advance_is_lineage_not_model1d_staleness(tmp_path: Path) -> None:
    write_boundary(tmp_path)

    class AdvancedSourceRepository(FakeRepository):
        def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
            frame = super().query_df(query, parameters)
            compact = " ".join(query.split()).lower()
            replacements = {
                "from forecast_registry": "gdp-new",
                "from inflation_live_runs": "inflation-new",
                "from labour_live_runs": "labour-new",
            }
            for marker, run_id in replacements.items():
                if marker in compact and not frame.empty:
                    frame = frame.copy()
                    frame.loc[:, "run_id"] = run_id
            return frame

    result = collect_platform_status(
        AdvancedSourceRepository(),
        as_of=date(2026, 8, 7),
        project_root=tmp_path,
    )

    model1d = result["components"].set_index("component").loc["1D"]
    detail = result["model1d"].iloc[0]
    readiness = result["readiness"].iloc[0]

    assert model1d["freshness_state"] == "frozen_prospective_observation"
    assert int(model1d["stale_source_count"]) == 0
    assert bool(model1d["ready"]) is True
    assert bool(detail["source_run_advance_detected"]) is True
    assert bool(detail["source_runs_match_latest"]) is False
    assert bool(readiness["model1d_shadow_valid"]) is True
    assert "model1d_shadow_current" not in readiness.index

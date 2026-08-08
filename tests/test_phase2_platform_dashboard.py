from __future__ import annotations

import pandas as pd

from macropulse.platform.dashboard import (
    change_table,
    component_table,
    forecast_table,
    provenance_table,
    snapshot_download_bytes,
)


def sample_snapshot() -> dict:
    return {
        "snapshot_schema_version": "1.0.0",
        "as_of": "2026-08-08",
        "snapshot_hash": "abc123",
        "readiness": {
            "production_sources_ready": True,
            "model1d_shadow_valid": True,
            "platform_ready_for_downstream": True,
        },
        "production": {
            "1A": {
                "component": {
                    "component": "1A",
                    "model_id": "US_GDP_NOWCAST_1A",
                    "model_version": "1.0.0",
                    "lifecycle_status": "production",
                    "freshness_state": "fresh",
                    "information_cutoff": "2026-08-08",
                    "data_as_of": "2026-07-01",
                    "target_period": "2026Q3",
                    "ready": True,
                    "stale_source_count": 0,
                },
                "forecasts": [
                    {
                        "target_series": "GDPC1",
                        "target_name": "Real GDP Growth",
                        "target_period": "2026Q3",
                        "forecast_stage": "early_quarter",
                        "stable_model_name": "Stable Stage Policy",
                        "stable_point_forecast": 2.4,
                        "lower_80": -0.5,
                        "upper_80": 5.3,
                    }
                ],
            },
            "1B": {"component": {}, "forecasts": []},
            "1C": {"component": {}, "forecasts": []},
        },
        "changes_since_previous_governed_run": {
            "1A": [
                {
                    "target_name": "Real GDP Growth",
                    "current_target_period": "2026Q3",
                    "previous_target_period": "2026Q2",
                    "current_forecast": 2.4,
                    "previous_forecast": None,
                    "forecast_change": None,
                    "comparable_forecast": False,
                    "target_period_changed": True,
                    "stage_changed": True,
                    "current_stage": "early_quarter",
                    "previous_stage": "quarter_end",
                }
            ],
            "1B": [],
            "1C": [],
        },
        "model1d": {
            "component": {
                "component": "1D",
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "lifecycle_status": "development",
                "freshness_state": "frozen_prospective_observation",
                "information_cutoff": "2026-08-05",
                "data_as_of": "2026-08-31",
                "target_period": "2026-08-31",
                "ready": True,
                "stale_source_count": 0,
            },
            "run": {
                "shadow_run_id": "shadow-aug",
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "information_cutoff": "2026-08-05",
                "state_date": "2026-08-31",
                "status": "predicted",
                "config_hash": "cfg",
                "code_hash": "code",
                "git_commit": "git",
                "information_set_hash": "info",
                "source_bundle_hash": "bundle",
            },
            "predictions": [],
            "dimensions": [],
            "status_detail": {
                "source_run_advance_detected": True,
                "outcome_count": 0,
                "complete_target_months": 0,
            },
        },
        "freshness": {"source_health": [], "due_releases": []},
        "calendar": {"upcoming_releases": []},
        "provenance": {
            "1A": {
                "run_id": "gdp-new",
                "model_id": "US_GDP_NOWCAST_1A",
                "model_version": "1.0.0",
                "information_cutoff": "2026-08-08",
            },
            "1B": {},
            "1C": {},
        },
    }


def test_component_table_keeps_model1d_research_state() -> None:
    frame = component_table(sample_snapshot()).set_index("component")
    assert frame.loc["1A", "state"] == "fresh"
    assert frame.loc["1D", "state"] == "frozen_prospective_observation"
    assert bool(frame.loc["1D", "ready"]) is True


def test_forecast_table_uses_snapshot_values() -> None:
    frame = forecast_table(sample_snapshot())
    assert len(frame) == 1
    assert frame.iloc[0]["series"] == "GDPC1"
    assert float(frame.iloc[0]["forecast"]) == 2.4


def test_change_table_preserves_non_comparability() -> None:
    frame = change_table(sample_snapshot())
    assert len(frame) == 1
    assert bool(frame.iloc[0]["comparable"]) is False
    assert bool(frame.iloc[0]["target_period_changed"]) is True
    assert pd.isna(frame.iloc[0]["forecast_change"])


def test_provenance_table_combines_production_and_model1d() -> None:
    frame = provenance_table(sample_snapshot()).set_index("component")
    assert frame.loc["1A", "run_id"] == "gdp-new"
    assert frame.loc["1D", "run_id"] == "shadow-aug"


def test_download_is_deterministic_snapshot_json() -> None:
    first = snapshot_download_bytes(sample_snapshot())
    second = snapshot_download_bytes(sample_snapshot())
    assert first == second
    assert b'"snapshot_hash": "abc123"' in first

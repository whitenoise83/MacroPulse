from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from macropulse.platform.snapshot import (
    build_macro_snapshot,
    canonical_json_bytes,
    semantic_snapshot_hash,
)


class FakeRepository:
    def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
        compact = " ".join(query.split()).lower()

        if "select run_id from forecast_registry" in compact:
            return pd.DataFrame([{"run_id": "gdp-old"}])
        if "select run_id from inflation_live_runs" in compact:
            return pd.DataFrame([{"run_id": "inf-old"}])
        if "select run_id from labour_live_runs" in compact:
            return pd.DataFrame([{"run_id": "lab-old"}])

        if "from forecast_registry" in compact and "champion_model" in compact:
            run_id = parameters[0]
            return pd.DataFrame([{
                "run_id": run_id,
                "target_period": "2026Q3" if run_id == "gdp-new" else "2026Q2",
                "forecast_stage": "early_quarter" if run_id == "gdp-new" else "quarter_end",
                "stable_model_name": "Stable Stage Policy",
                "stable_point_forecast": 2.4 if run_id == "gdp-new" else 1.8,
                "lower_80": -0.6,
                "upper_80": 5.4,
            }])

        if "from inflation_live_forecasts" in compact:
            run_id = parameters[0]
            return pd.DataFrame([{
                "run_id": run_id,
                "target_series": "CPILFESL",
                "target_name": "Core CPI",
                "target_unit": None,
                "target_period": "2026-07",
                "forecast_stage": "month_end",
                "stable_model_name": "Inflation Ridge-AR Ensemble",
                "stable_point_forecast": 0.85 if run_id == "inf-new" else 0.75,
                "lower_80": -0.9,
                "upper_80": 2.6,
                "shadow_model_name": "Inflation AR(1)",
                "shadow_point_forecast": 0.67,
            }])

        if "from labour_live_forecasts" in compact:
            run_id = parameters[0]
            return pd.DataFrame([{
                "run_id": run_id,
                "target_series": "UNRATE",
                "target_name": "Unemployment Rate",
                "target_unit": "percent",
                "target_period": "2026-08",
                "forecast_stage": "after_week_1",
                "stable_model_name": "Labour Equal-Weight Ensemble",
                "stable_point_forecast": 4.0 if run_id == "lab-new" else 4.1,
                "lower_80": 3.6,
                "upper_80": 4.4,
                "shadow_model_name": "Labour AR(1)",
                "shadow_point_forecast": 4.29,
            }])

        if "from forecast_registry" in compact and "config_hash" in compact:
            return pd.DataFrame([{
                "run_id": "gdp-new",
                "model_id": "US_GDP_NOWCAST_1A",
                "model_version": "1.0.0",
                "config_hash": "cfg-a",
                "code_hash": "code-a",
                "git_commit": "abc",
                "information_set_hash": "info-a",
                "information_cutoff": date(2026, 8, 8),
                "data_as_of": date(2026, 7, 1),
                "target_period": "2026Q3",
                "forecast_stage": "early_quarter",
                "status": "success",
            }])

        if "from inflation_live_runs" in compact and "governance_signature" in compact:
            return pd.DataFrame([{
                "run_id": "inf-new",
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "1.0.0",
                "information_cutoff": date(2026, 8, 8),
                "data_as_of": date(2026, 8, 7),
                "status": "success",
                "candidate_validation_id": "v1",
                "backtest_id": "b1",
                "config_hash": "cfg-b",
                "code_hash": "code-b",
                "git_commit": "abc",
                "information_set_hash": "info-b",
                "model_state_hash": "state-b",
                "governance_signature": "gov-b",
            }])

        if "from labour_live_runs" in compact and "governance_signature" in compact:
            return pd.DataFrame([{
                "run_id": "lab-new",
                "model_id": "US_LABOUR_NOWCAST_1C",
                "model_version": "1.0.0",
                "information_cutoff": date(2026, 8, 8),
                "data_as_of": date(2026, 8, 1),
                "status": "success",
                "candidate_validation_id": "v2",
                "backtest_id": "b2",
                "config_hash": "cfg-c",
                "code_hash": "code-c",
                "git_commit": "abc",
                "information_set_hash": "info-c",
                "model_state_hash": "state-c",
                "governance_signature": "gov-c",
            }])

        if "from macro_state_shadow_runs" in compact:
            return pd.DataFrame([{
                "shadow_run_id": "shadow-aug",
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "state_date": date(2026, 8, 31),
                "information_cutoff": date(2026, 8, 5),
                "target_mode": "fixed_horizon",
                "target_horizon_days": 90,
                "target_expected_available_date": date(2026, 11, 29),
                "source_candidate_id": "candidate",
                "source_evidence_version": "v0.3.7",
                "primary_comparator": "rolling_frequency",
                "source_macro_state_run_id": "state-source",
                "gdp_run_id": "gdp-source",
                "inflation_run_id": "inf-source",
                "labour_run_id": "lab-source",
                "config_hash": "cfg-d",
                "code_hash": "code-d",
                "git_commit": "abc",
                "information_set_hash": "info-d",
                "source_bundle_hash": "bundle",
                "no_look_ahead_pass": True,
                "status": "predicted",
            }])

        if "from macro_state_shadow_predictions" in compact:
            return pd.DataFrame([{
                "benchmark_id": "source",
                "predicted_family": "contraction",
                "predicted_probabilities_json": json.dumps({
                    "contraction": 0.44,
                    "benign_expansion": 0.20,
                }),
                "top1_family": "contraction",
                "top2_family": "benign_expansion",
                "top3_family": "mixed",
                "top1_probability": 0.44,
                "top2_probability": 0.20,
                "top3_probability": 0.15,
                "top1_top2_gap": 0.24,
                "entropy": 1.3,
                "probability_sum": 1.0,
                "probability_vector_hash": "prob",
                "no_look_ahead_pass": True,
            }])

        if "from macro_state_shadow_dimensions" in compact:
            return pd.DataFrame([{
                "dimension": "growth",
                "score": -0.2,
                "lower_score": -1.0,
                "upper_score": 0.7,
                "label": "weak",
                "confidence": 0.4,
                "source_model_id": "US_GDP_NOWCAST_1A",
                "source_model_version": "1.0.0",
                "source_run_id": "gdp-source",
                "source_information_cutoff": date(2026, 8, 5),
                "source_data_as_of": date(2026, 6, 1),
                "source_hash": "hash",
                "no_look_ahead_pass": True,
            }])

        raise AssertionError(f"Unexpected query: {compact}")


def fake_status(repository, *, as_of, project_root):
    components = pd.DataFrame([
        {
            "component": "1A", "model_id": "US_GDP_NOWCAST_1A",
            "model_version": "1.0.0", "lifecycle_status": "production",
            "run_id": "gdp-new", "information_cutoff": date(2026, 8, 8),
            "data_as_of": date(2026, 7, 1), "target_period": "2026Q3",
            "forecast_stage": "early_quarter", "target_count": 1,
            "source_series_count": 9, "stale_source_count": 0,
            "due_release_count": 0, "freshness_state": "fresh", "ready": True,
        },
        {
            "component": "1B", "model_id": "US_INFLATION_NOWCAST_1B",
            "model_version": "1.0.0", "lifecycle_status": "production",
            "run_id": "inf-new", "information_cutoff": date(2026, 8, 8),
            "data_as_of": date(2026, 8, 7), "target_period": None,
            "forecast_stage": None, "target_count": 1,
            "source_series_count": 13, "stale_source_count": 0,
            "due_release_count": 0, "freshness_state": "fresh", "ready": True,
        },
        {
            "component": "1C", "model_id": "US_LABOUR_NOWCAST_1C",
            "model_version": "1.0.0", "lifecycle_status": "production",
            "run_id": "lab-new", "information_cutoff": date(2026, 8, 8),
            "data_as_of": date(2026, 8, 1), "target_period": None,
            "forecast_stage": None, "target_count": 1,
            "source_series_count": 13, "stale_source_count": 0,
            "due_release_count": 0, "freshness_state": "fresh", "ready": True,
        },
        {
            "component": "1D", "model_id": "US_MACRO_STATE_1D",
            "model_version": "0.3.8", "lifecycle_status": "development",
            "run_id": "shadow-aug", "information_cutoff": date(2026, 8, 5),
            "data_as_of": date(2026, 8, 31), "target_period": "2026-08-31",
            "forecast_stage": "prospective_shadow", "target_count": 2,
            "source_series_count": 3, "stale_source_count": 0,
            "due_release_count": 0,
            "freshness_state": "frozen_prospective_observation", "ready": True,
        },
    ])
    return {
        "as_of": as_of,
        "components": components,
        "source_health": pd.DataFrame([{
            "component": "1A", "run_id": "gdp-new", "series_id": "GDPC1",
            "frequency": "Q", "latest_observation_date": date(2026, 4, 1),
            "age_days": 129, "threshold_days": 180,
            "release_due_since_run": False, "freshness_state": "fresh",
            "stale": False,
        }]),
        "due_releases": pd.DataFrame(),
        "upcoming_releases": pd.DataFrame([{
            "series_id": "CPIAUCSL", "release_id": 10,
            "release_name": "Consumer Price Index",
            "release_date": date(2026, 8, 12), "days_until_release": 4,
        }]),
        "model1d": pd.DataFrame([{
            "shadow_run_id": "shadow-aug", "state_date": date(2026, 8, 31),
            "information_cutoff": date(2026, 8, 5),
            "target_expected_available_date": date(2026, 11, 29),
            "source_runs_match_latest": False,
            "source_run_advance_detected": True,
            "no_look_ahead_pass": True, "outcome_count": 0,
            "complete_target_months": 0,
            "shadow_state": "frozen_prospective_observation",
        }]),
        "readiness": pd.DataFrame([{
            "production_sources_ready": True, "model1d_shadow_valid": True,
            "platform_ready_for_downstream": True, "blocking_components": "",
            "next_action": "no_model_action_required",
        }]),
    }


def test_snapshot_is_semantically_deterministic(tmp_path: Path) -> None:
    first = build_macro_snapshot(
        FakeRepository(), as_of=date(2026, 8, 8),
        project_root=tmp_path, status_provider=fake_status,
    )
    second = build_macro_snapshot(
        FakeRepository(), as_of=date(2026, 8, 8),
        project_root=tmp_path, status_provider=fake_status,
    )
    assert first == second
    assert first["snapshot_hash"] == second["snapshot_hash"]
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_period_change_is_not_presented_as_forecast_revision(tmp_path: Path) -> None:
    snapshot = build_macro_snapshot(
        FakeRepository(), as_of=date(2026, 8, 8),
        project_root=tmp_path, status_provider=fake_status,
    )
    change = snapshot["changes_since_previous_governed_run"]["1A"][0]
    assert change["target_period_changed"] is True
    assert change["comparable_forecast"] is False
    assert change["forecast_change"] is None


def test_comparable_live_forecast_gets_numeric_change(tmp_path: Path) -> None:
    snapshot = build_macro_snapshot(
        FakeRepository(), as_of=date(2026, 8, 8),
        project_root=tmp_path, status_provider=fake_status,
    )
    change = snapshot["changes_since_previous_governed_run"]["1B"][0]
    assert change["comparable_forecast"] is True
    assert round(change["forecast_change"], 10) == 0.1


def test_model1d_is_read_from_frozen_shadow_tables(tmp_path: Path) -> None:
    snapshot = build_macro_snapshot(
        FakeRepository(), as_of=date(2026, 8, 8),
        project_root=tmp_path, status_provider=fake_status,
    )
    assert snapshot["model1d"]["component"]["run_id"] == "shadow-aug"
    assert snapshot["model1d"]["status_detail"]["source_run_advance_detected"] is True
    assert snapshot["model1d"]["predictions"][0]["predicted_family"] == "contraction"
    assert snapshot["model1d"]["predictions"][0]["predicted_probabilities"]["contraction"] == 0.44


def test_hash_changes_when_semantic_content_changes() -> None:
    assert semantic_snapshot_hash(
        {"as_of": "2026-08-08", "value": 1}
    ) != semantic_snapshot_hash(
        {"as_of": "2026-08-08", "value": 2}
    )

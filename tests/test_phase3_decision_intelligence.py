from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from macropulse.evaluation.decision import (
    build_decision_intelligence_snapshot,
)


ROOT = Path(__file__).parents[1]


def fake_platform(*args, **kwargs):
    return {
        "snapshot_hash": "platform-hash",
        "readiness": {
            "production_sources_ready": True,
            "platform_ready_for_downstream": True,
        },
        "production": {
            "1A": {
                "component": {
                    "model_id": "US_GDP_NOWCAST_1A",
                    "model_version": "1.0.0",
                    "run_id": "gdp",
                    "information_cutoff": "2026-08-08",
                    "data_as_of": "2026-07-01",
                    "freshness_state": "fresh",
                    "ready": True,
                },
                "forecasts": [
                    {
                        "target_series": "GDPC1",
                        "target_name": "Real GDP Growth",
                        "target_period": "2026Q3",
                        "forecast_stage": "early_quarter",
                        "stable_point_forecast": 2.4,
                        "lower_80": -0.6,
                        "upper_80": 5.4,
                    }
                ],
            },
            "1B": {"component": {}, "forecasts": []},
            "1C": {"component": {}, "forecasts": []},
        },
        "freshness": {"source_health": [], "due_releases": []},
        "calendar": {"upcoming_releases": []},
        "provenance": {},
        "model1d": {
            "component": {"model_id": "US_MACRO_STATE_1D"},
            "run": None,
            "status_detail": {},
        },
    }


def fake_ledger(*args, **kwargs):
    return pd.DataFrame(
        [
            {
                "evaluation_id": "e",
                "forecast_identity": "f",
                "evaluation_as_of": date(2026, 8, 10),
                "component": "1A",
                "model_id": "US_GDP_NOWCAST_1A",
                "model_version": "1.0.0",
                "run_id": "gdp",
                "information_cutoff": date(2026, 8, 8),
                "data_as_of": date(2026, 7, 1),
                "target_series": "GDPC1",
                "target_name": "Real Gross Domestic Product",
                "target_period": "2026Q3",
                "forecast_stage": "early_quarter",
                "forecast_model_name": "stable",
                "forecast_value": 2.4,
                "lower_80": -0.6,
                "upper_80": 5.4,
                "interval_width": 6.0,
                "estimated_release_date": None,
                "outcome_definition": "initial_release_transformed_target",
                "outcome_vintage": "first_release",
                "outcome_evidence_source": None,
                "outcome_release_date": None,
                "outcome_value": None,
                "evaluation_status": "unresolved_outcome_not_yet_available",
                "status_detail": "pending",
                "no_look_ahead_pass": None,
                "lead_days": None,
                "signed_error": None,
                "absolute_error": None,
                "squared_error": None,
                "interval_covered": None,
            }
        ]
    )


def fake_revisions(*args, **kwargs):
    columns = [
        "revision_id",
        "component",
        "model_id",
        "model_version",
        "target_series",
        "target_name",
        "target_period",
        "comparison_status",
        "current_run_id",
        "current_information_cutoff",
        "current_data_as_of",
        "current_forecast_stage",
        "current_forecast_value",
        "current_lower_80",
        "current_upper_80",
        "current_interval_width",
        "previous_run_id",
        "previous_information_cutoff",
        "previous_data_as_of",
        "previous_forecast_stage",
        "previous_forecast_value",
        "previous_lower_80",
        "previous_upper_80",
        "previous_interval_width",
        "first_run_id",
        "first_information_cutoff",
        "first_forecast_value",
        "revision",
        "absolute_revision",
        "revision_direction",
        "cumulative_revision",
        "absolute_cumulative_revision",
        "lower_80_revision",
        "upper_80_revision",
        "interval_width_revision",
        "stage_changed",
        "days_between_runs",
        "associated_release_count",
        "advanced_source_release_count",
        "release_association_state",
        "associated_release_labels",
    ]
    return {
        "revisions": pd.DataFrame(columns=columns),
        "release_events": pd.DataFrame(
            columns=[
                "revision_id",
                "component",
                "target_series",
                "target_period",
                "previous_run_id",
                "current_run_id",
                "previous_information_cutoff",
                "current_information_cutoff",
                "release_date",
                "series_id",
                "release_id",
                "release_name",
                "previous_latest_observation_date",
                "current_latest_observation_date",
                "information_set_advanced",
                "association_type",
                "causality_claim",
            ]
        ),
    }


def test_snapshot_is_deterministic_and_separates_model1d() -> None:
    first = build_decision_intelligence_snapshot(
        object(),
        as_of=date(2026, 8, 10),
        project_root=ROOT,
        macro_snapshot_provider=fake_platform,
        ledger_provider=fake_ledger,
        revision_provider=fake_revisions,
    )
    second = build_decision_intelligence_snapshot(
        object(),
        as_of=date(2026, 8, 10),
        project_root=ROOT,
        macro_snapshot_provider=fake_platform,
        ledger_provider=fake_ledger,
        revision_provider=fake_revisions,
    )
    assert first == second
    assert first["snapshot_hash"] == second["snapshot_hash"]
    assert first["contract"]["automatic_model_action"] == "none"
    assert first["contract"]["generative_ai_in_governed_core"] is False
    assert (
        first["model1d_research"]["separation"]
        == "research_only_no_production_evaluation_authority"
    )
    assert first["summary"]["current_target_count"] == 1


def test_no_history_becomes_evidence_flag_not_performance_judgement() -> None:
    snapshot = build_decision_intelligence_snapshot(
        object(),
        as_of=date(2026, 8, 10),
        project_root=ROOT,
        macro_snapshot_provider=fake_platform,
        ledger_provider=fake_ledger,
        revision_provider=fake_revisions,
    )
    flags = snapshot["evidence_flags"]
    assert any(
        row["code"] == "no_resolved_evaluation_history"
        and row["target_series"] == "GDPC1"
        for row in flags
    )
    assert all("bad" not in row["detail"].lower() for row in flags)


def test_future_as_of_fails_closed() -> None:
    import pytest

    with pytest.raises(ValueError, match="future"):
        build_decision_intelligence_snapshot(
            object(),
            as_of=date(2999, 1, 1),
            project_root=ROOT,
            macro_snapshot_provider=fake_platform,
            ledger_provider=fake_ledger,
            revision_provider=fake_revisions,
        )

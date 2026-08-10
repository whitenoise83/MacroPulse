from __future__ import annotations

from macropulse.evaluation.dashboard import (
    comparable_revision_table,
    current_forecast_table,
    evidence_flag_table,
    model1d_research_summary,
)


def test_dashboard_helpers_are_pure_snapshot_transforms() -> None:
    snapshot = {
        "current_forecasts": [
            {"component": "1B", "target_series": "CPIAUCSL"}
        ],
        "evidence_flags": [
            {"severity": "info", "code": "insufficient_evaluation_history"}
        ],
        "revisions": {
            "revisions": [
                {
                    "comparison_status": "baseline_no_previous",
                    "target_series": "CPIAUCSL",
                },
                {
                    "comparison_status": "comparable_revision",
                    "target_series": "CPIAUCSL",
                },
            ]
        },
        "model1d_research": {
            "evidence": {
                "component": {"model_id": "US_MACRO_STATE_1D"},
                "run": {"model_version": "0.3.8", "state_date": "2026-08-31"},
                "status_detail": {"complete_target_months": 0, "outcome_count": 0},
            }
        },
    }
    assert len(current_forecast_table(snapshot)) == 1
    assert len(evidence_flag_table(snapshot)) == 1
    assert len(comparable_revision_table(snapshot)) == 1
    model1d = model1d_research_summary(snapshot)
    assert model1d.iloc[0]["promotion_authority"] == "none"

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = json.loads((ROOT / "PHASE3_RELEASE.json").read_text(encoding="utf-8"))
BOUNDARY = json.loads((ROOT / "PHASE3_BOUNDARY.json").read_text(encoding="utf-8"))


def test_phase3_release_identity_and_roadmap_context() -> None:
    assert RELEASE["internal_phase"] == "III"
    assert RELEASE["roadmap_phase"] == "I"
    assert RELEASE["platform_version"] == "1.0.0"
    assert RELEASE["status"] == "released"
    assert RELEASE["release_tag"] == "phase3-evaluation-v1.0.0"
    assert RELEASE["release_branch"] == "phase3-evaluation-development"
    assert "not roadmap Phase III" in RELEASE["roadmap_note"]


def test_phase3_release_records_green_source_gate() -> None:
    source = RELEASE["closure_source_commit"]
    assert source["sha"] == "ac8af6425cdb79e1516614328b52ab761be1ffe4"
    ci = RELEASE["ci_evidence"]["phase3_evaluation_guard"]
    assert ci["workflow"] == "Phase III Evaluation Guard"
    assert ci["run_number"] == 1
    assert ci["run_id"] == 31425130485
    assert ci["job_id"] == 93574903444
    assert ci["status"] == "completed"
    assert ci["conclusion"] == "success"
    assert ci["head_sha"] == source["sha"]


def test_phase3_release_preserves_model_authority_boundaries() -> None:
    assert BOUNDARY["status"] == "released"
    assert BOUNDARY["phase3_may_change_model_specifications"] is False
    assert BOUNDARY["phase3_may_mutate_governed_forecasts"] is False
    assert BOUNDARY["phase3_may_tune_model1d_on_prospective_outcomes"] is False
    assert BOUNDARY["phase3_core_may_use_generative_ai"] is False
    assert BOUNDARY["model_suite"]["1D"]["promotion_authority"] == "none"
    assert RELEASE["execution_authority"] == {
        "automatic_model_action": "none",
        "governed_forecast_mutation": "none",
        "model_execution": "none",
        "model1d_promotion_authority": "none",
    }


def test_phase3_release_snapshot_evidence_is_frozen() -> None:
    evidence = RELEASE["deterministic_snapshot_evidence"]
    assert evidence["as_of"] == "2026-08-10"
    assert evidence["snapshot_hash"] == (
        "8a8dca1095109d9ea3d2540ee264cae407598847117bd5dd1a4f6ef9dfd5ce11"
    )

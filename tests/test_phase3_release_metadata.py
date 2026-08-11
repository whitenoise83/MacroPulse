from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
RELEASE = json.loads((ROOT / "PHASE3_RELEASE.json").read_text(encoding="utf-8"))
BOUNDARY = json.loads((ROOT / "PHASE3_BOUNDARY.json").read_text(encoding="utf-8"))

def test_phase3_release_identity_and_roadmap_context() -> None:
    assert RELEASE["internal_phase"] == "III"
    assert RELEASE["roadmap_phase"] == "I"
    assert RELEASE["platform_version"] == "1.0.1"
    assert RELEASE["release_type"] == "release_engineering_patch"
    assert RELEASE["semantic_change"] is False
    assert RELEASE["release_tag"] == "phase3-evaluation-v1.0.1"

def test_previous_v100_release_is_immutable() -> None:
    previous = RELEASE["previous_release"]
    assert previous["tag"] == "phase3-evaluation-v1.0.0"
    assert previous["commit"] == "20c3682a96061d9e740aaf001bf2f72a98377928"
    assert previous["immutable"] is True
    assert previous["move_or_recreate"] is False

def test_v101_source_gate_is_green_run_2() -> None:
    source = RELEASE["closure_source_commit"]
    assert source["sha"] == "20c3682a96061d9e740aaf001bf2f72a98377928"
    ci = RELEASE["ci_evidence"]["phase3_evaluation_guard"]
    assert ci["run_number"] == 2
    assert ci["run_id"] == 31428781570
    assert ci["job_id"] == 93586783076
    assert ci["conclusion"] == "success"

def test_v100_tag_ci_failure_is_recorded() -> None:
    failure = RELEASE["prior_tag_ci_failure"]
    assert failure["run_number"] == 3
    assert failure["run_id"] == 31470015299
    assert failure["job_id"] == 93711061207
    assert failure["failure_scope"] == "release_test_contract_only"
    assert failure["model_or_evaluation_semantics_affected"] is False

def test_model_authority_boundaries_unchanged() -> None:
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

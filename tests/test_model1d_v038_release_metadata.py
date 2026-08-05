from __future__ import annotations

import json
from pathlib import Path

from macropulse.macro_state.versioning import load_macro_state_governance


ROOT = Path(__file__).parents[1]


def test_v038_release_metadata_preserves_research_boundary() -> None:
    release = json.loads(
        (ROOT / "MODEL1D_v0.3.8_RELEASE.json").read_text(encoding="utf-8")
    )
    assert release["model_id"] == "US_MACRO_STATE_1D"
    assert release["version"] == "0.3.8"
    assert release["lifecycle_status"] == "development"
    assert release["release_status"] == "prospective_shadow_operational_research_only"
    assert release["promotion_authority"] == "none"
    assert release["promotion_approved"] is False
    assert release["switching_approved"] is False
    assert release["blending_approved"] is False
    assert release["source_replacement_approved"] is False
    assert release["formal_comparison_permitted_at_freeze"] is False
    assert release["current_conclusion"] == "insufficient_prospective_evidence"


def test_v038_release_metadata_matches_governance() -> None:
    release = json.loads(
        (ROOT / "MODEL1D_v0.3.8_RELEASE.json").read_text(encoding="utf-8")
    )
    config = load_macro_state_governance()
    section = config["prospective_transition_shadow"]
    assert release["version"] == str(section["model_version"])
    assert release["frozen_source_version"] == str(
        section["frozen_source"]["model_version"]
    )
    assert release["frozen_source_candidate"] == str(
        section["frozen_source"]["candidate_id"]
    )
    assert release["primary_comparator"] == str(
        section["comparator"]["benchmark_id"]
    )
    assert release["target_mode"] == str(section["target"]["mode"])
    assert release["target_horizon_days"] == int(section["target"]["horizon_days"])
    assert release["minimum_complete_target_months"] == int(
        section["minimum_evidence"]["complete_target_months"]
    )
    assert release["promotion_authority"] == str(section["promotion_authority"])


def test_v038_first_prospective_identity_is_frozen() -> None:
    release = json.loads(
        (ROOT / "MODEL1D_v0.3.8_RELEASE.json").read_text(encoding="utf-8")
    )
    assert release["first_shadow_run_id"] == (
        "73ea26fd-a731-4d87-a735-ae1107a9c06c"
    )
    assert release["first_information_cutoff"] == "2026-08-05"
    assert release["first_state_date"] == "2026-08-31"
    assert release["first_expected_target_availability_date"] == "2026-11-29"
    assert release["first_outcome_rows_at_freeze"] == 0
    assert release["operational_commit"] == "6e1ff2a"
    assert release["operational_tag"] == (
        "model1d-v0.3.8-prospective-shadow-operational"
    )


def test_v038_release_documentation_is_present_and_consistent() -> None:
    readme = (ROOT / "README_MODEL1D_v0.3.8.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG_MODEL1D_v0.3.8.md").read_text(
        encoding="utf-8"
    )
    validation = (ROOT / "VALIDATION_MODEL1D_v0.3.8.txt").read_text(
        encoding="utf-8"
    )
    top_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "promotion authority: `none`" in readme.lower()
    assert "12 complete prospective target months" in readme
    assert "insufficient_prospective_evidence" in readme
    assert "Operational tag" in changelog
    assert "29 passed" in validation
    assert "Model 1C — US Labour Nowcast:** production v1.0.0" in top_readme
    assert "Model 1D — Unified US Macro State:** development v0.3.8" in top_readme


def test_v038_release_does_not_commit_local_database_artifacts() -> None:
    release = json.loads(
        (ROOT / "MODEL1D_v0.3.8_RELEASE.json").read_text(encoding="utf-8")
    )
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert release["database_artifacts_committed"] is False
    assert "data/backups/" in gitignore
    assert "reports/macro_state_shadow_monitoring/" in gitignore

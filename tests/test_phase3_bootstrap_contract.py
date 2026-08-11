from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
BOUNDARY = ROOT / "PHASE3_BOUNDARY.json"
PLAN = ROOT / "MACROPULSE_PHASE3_PLAN.md"
ARCHITECTURE = ROOT / "docs" / "PHASE3_ARCHITECTURE.md"

EXPECTED_BRANCH = "phase3-evaluation-development"
EXPECTED_BASE_TAG = "phase2-platform-v1.0.0"
EXPECTED_BASE_COMMIT = "43395d889a76453706259a5095bd718337b55851"
RELEASE_TAG_PATTERN = re.compile(r"^phase3-evaluation-v\d+\.\d+\.\d+$")


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def test_phase3_boundary_identity() -> None:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    assert payload["phase"] == "III"
    assert payload["branch"] == EXPECTED_BRANCH
    assert payload["base_release_tag"] == EXPECTED_BASE_TAG
    assert payload["base_release_commit"] == EXPECTED_BASE_COMMIT


def test_phase2_release_tag_still_points_to_frozen_base() -> None:
    tag_commit = git("rev-parse", f"{EXPECTED_BASE_TAG}^{{commit}}")
    assert tag_commit == EXPECTED_BASE_COMMIT


def test_current_checkout_is_phase3_development_or_release_tag() -> None:
    branch = git("branch", "--show-current")
    if branch:
        assert branch == EXPECTED_BRANCH
        return

    tags = [tag for tag in git("tag", "--points-at", "HEAD").splitlines() if tag]
    assert any(RELEASE_TAG_PATTERN.fullmatch(tag) for tag in tags)


def test_phase3_descends_from_phase2_release() -> None:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_model_governance_boundaries_are_fail_closed() -> None:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    assert payload["phase3_may_change_model_specifications"] is False
    assert payload["phase3_may_tune_model1d_on_prospective_outcomes"] is False
    assert payload["phase3_may_backfill_model1d"] is False
    assert payload["phase3_may_move_model1d_release_tags"] is False
    assert payload["phase3_may_move_phase2_release_tag"] is False
    assert payload["phase3_may_automatically_promote_or_demote_models"] is False
    assert payload["phase3_may_mutate_governed_forecasts"] is False
    assert payload["phase3_core_may_use_generative_ai"] is False


def test_outcome_vintage_and_no_look_ahead_are_mandatory() -> None:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    rules = payload["evaluation_rules"]
    assert rules["outcome_vintage_must_be_explicit"] is True
    assert rules["first_release_default_where_defined"] is True
    assert rules["revised_outcomes_separately_labelled"] is True
    assert rules["no_look_ahead_required"] is True
    assert rules["monitoring_is_not_adaptation"] is True


def test_phase3_bootstrap_documents_exist() -> None:
    assert PLAN.is_file()
    assert ARCHITECTURE.is_file()

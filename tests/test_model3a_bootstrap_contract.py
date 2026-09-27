from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[1]
BOUNDARY = ROOT / "MODEL3_BOUNDARY.json"
BRANCH = "model3-output-gap-development"
TAG = "model2-bvar-v1.0.2"
COMMIT = "cda24988e772cd2b96be612b7d455c54a06f44fa"

def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()

def payload() -> dict:
    return json.loads(BOUNDARY.read_text(encoding="utf-8"))

def test_identity() -> None:
    data = payload()
    assert data["roadmap_phase"] == "II"
    assert data["model"] == "3"
    assert data["model_name"] == "Potential Output & Macroeconomic Slack"
    assert data["status"] == "specification_bootstrap"
    assert data["promotion_authority"] == "none"

def test_branch_and_immutable_base_metadata() -> None:
    data = payload()
    assert data["branch"] == BRANCH
    assert data["base_release_tag"] == TAG
    assert data["base_release_commit"] == COMMIT
    assert git("rev-parse", TAG + "^{commit}") == COMMIT

def test_model3_descends_from_immutable_model2_release() -> None:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", COMMIT, "HEAD"],
        cwd=ROOT, capture_output=True, text=True
    )
    assert completed.returncode == 0

def test_fail_closed_governance() -> None:
    governance = payload()["governance"]
    assert governance
    assert all(value is False for key, value in governance.items() if key.startswith("model3_"))

def test_real_time_contract() -> None:
    rt = payload()["real_time_contract"]
    assert rt["pseudo_real_time_required"]
    assert rt["information_set_cutoff_required"]
    assert rt["vintage_identity_required"]
    assert rt["no_look_ahead_required"]
    assert rt["latest_revised_data_may_not_masquerade_as_real_time"]
    assert rt["revised_or_smoothed_estimates_separately_labelled"]
    assert rt["monitoring_is_not_adaptation"]

def test_core_outputs_and_horizons() -> None:
    contract = payload()["core_output_contract"]
    assert contract["objects"] == [
        "potential_output_level",
        "potential_output_growth",
        "output_gap_pct",
        "output_gap_uncertainty",
    ]
    assert contract["forward_horizons_quarters"] == [0, 1, 2, 4, 8]
    assert contract["real_time_estimate_required"]
    assert contract["uncertainty_required"]

def test_candidate_architecture_does_not_freeze_winner() -> None:
    candidate = payload()["candidate_architecture"]
    assert candidate["production_winner_frozen_in_3a"] is False
    assert candidate["core_family"] == "state_space_unobserved_components"
    assert candidate["prospective_adaptation"] is False
    assert "hamilton_regression_filter" in candidate["benchmark_families"]

def test_model2_circularity_firewall() -> None:
    integration = payload()["integration_contract"]
    assert integration["model1_interface_frozen_in"] == "3F"
    assert integration["model2_interface_frozen_in"] == "3G"
    assert integration["model2_forecasts_may_determine_current_or_historical_potential"] is False
    assert integration["model2_forecasts_may_retune_model3_current_or_historical_estimator"] is False
    assert integration["forward_gap_distribution_requires_separately_governed_potential_process"] is True

def test_bootstrap_scope() -> None:
    bootstrap = payload()["bootstrap_contract"]
    assert bootstrap["new_paths_only"] is True
    assert bootstrap["predecessor_file_modification_allowed"] is False
    assert bootstrap["passing_3a_authorizes_only"] == "3B_real_time_data_vintages"

def test_docs_and_verifier_exist() -> None:
    assert (ROOT / "MACROPULSE_MODEL3_PLAN.md").is_file()
    assert (ROOT / "docs/MODEL3A_SLACK_SPECIFICATION_CONTRACT.md").is_file()
    assert (ROOT / "scripts/verify_model3a_bootstrap.py").is_file()

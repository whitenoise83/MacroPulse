from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
BOUNDARY = ROOT / "MODEL2_BOUNDARY.json"
BRANCH = "model2-bvar-development"
TAG = "phase3-evaluation-v1.0.1"
COMMIT = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def payload() -> dict:
    return json.loads(BOUNDARY.read_text(encoding="utf-8"))


def test_identity() -> None:
    data = payload()
    assert data["roadmap_phase"] == "II"
    assert data["model"] == "2"
    assert data["status"] == "specification_bootstrap"
    assert data["promotion_authority"] == "none"


def test_branch_base() -> None:
    data = payload()
    assert data["branch"] == BRANCH
    assert data["base_release_tag"] == TAG
    assert data["base_release_commit"] == COMMIT
    assert git("branch", "--show-current") == BRANCH
    assert git("rev-parse", TAG + "^{commit}") == COMMIT


def test_model2_descends_from_immutable_phase3_release() -> None:
    assert git("rev-parse", TAG + "^{commit}") == COMMIT
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", COMMIT, "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0


def test_model1_fail_closed() -> None:
    governance = payload()["governance"]
    assert all(
        value is False
        for key, value in governance.items()
        if key.startswith("model2_") or key.startswith("scenario_")
    )


def test_release_guard_maintenance_is_narrow_and_fail_closed() -> None:
    maintenance = payload()["bootstrap_release_guard_maintenance"]
    assert maintenance["allowed_paths"] == ["tests/test_phase3_bootstrap_contract.py"]
    assert maintenance["phase3_release_tag_may_move"] is False
    assert maintenance["phase3_evaluation_semantics_changed"] is False
    assert maintenance["model_semantics_changed"] is False


def test_real_time_contract() -> None:
    forecast = payload()["forecast_contract"]
    assert forecast["pseudo_real_time_required"]
    assert forecast["outcome_vintage_must_be_explicit"]
    assert forecast["first_release_default_where_defined"]
    assert forecast["revised_outcomes_must_be_separately_labelled"]
    assert forecast["no_look_ahead_required"]


def test_system() -> None:
    system = payload()["initial_endogenous_system"]
    assert [item["series_id"] for item in system] == [
        "GDPC1",
        "PCEPILFE",
        "UNRATE",
        "FEDFUNDS",
    ]


def test_prior_grid() -> None:
    spec = payload()["initial_bvar_specification"]
    assert spec["lag_candidates"] == [2, 4]
    assert spec["overall_shrinkage_candidates"] == [0.1, 0.2, 0.4]
    assert spec["prospective_adaptation"] is False


def test_structural_contract() -> None:
    structural = payload()["structural_analysis"]
    assert structural["baseline_identification"] == "recursive_cholesky"
    assert structural["recursive_order"] == [
        "real_gdp_growth",
        "core_pce_inflation",
        "unemployment_rate",
        "policy_rate",
    ]
    assert structural["causal_language_requires_identification_assumptions"]


def test_evaluation() -> None:
    evaluation = payload()["evaluation_contract"]
    assert evaluation["point_metrics"] == ["rmse", "mae", "bias"]
    assert "log_predictive_density" in evaluation["probabilistic_metrics"]
    assert "crps" in evaluation["probabilistic_metrics"]
    assert "classical_var" in evaluation["benchmark_families"]
    assert evaluation["monitoring_is_not_adaptation"]


def test_docs() -> None:
    assert (ROOT / "MACROPULSE_MODEL2_PLAN.md").is_file()
    assert (ROOT / "docs/MODEL2A_BVAR_SPECIFICATION_CONTRACT.md").is_file()
    assert (ROOT / "scripts/verify_model2a_bootstrap.py").is_file()

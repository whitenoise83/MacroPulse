from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "model3-output-gap-development"
MODEL2_TAG = "model2-bvar-v1.0.2"
MODEL2_COMMIT = "cda24988e772cd2b96be612b7d455c54a06f44fa"
MODEL3C_COMMIT = "dfcee48d0a0391f3187cf103c7c906d4ecf78892"

EXPECTED = {
    "MODEL3D_STATE_SPACE_CONTRACT.json",
    "docs/MODEL3D_STATE_SPACE_CONTRACT.md",
    "scripts/verify_model3d_state_space.py",
    "src/macropulse/slack/state_space.py",
    "tests/test_model3d_contract.py",
    "tests/test_model3d_state_space.py",
}

IGNORED_UNTRACKED_PREFIXES = (
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
    "reports/decision_intelligence_snapshots/",
    "data/backups/",
    "src/macropulse.egg-info/",
)


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def fail(message: str) -> None:
    raise SystemExit("Model 3D state-space verification: FAIL\n" + message)


def main() -> None:
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch not in {BRANCH, "HEAD"}:
        fail(f"Expected {BRANCH} or detached HEAD; found {branch}.")

    if git("rev-parse", MODEL2_TAG + chr(94) + "{commit}") != MODEL2_COMMIT:
        fail("Immutable Model 2 tag does not peel to the governed commit.")

    if git("merge-base", MODEL3C_COMMIT, "HEAD") != MODEL3C_COMMIT:
        fail("HEAD is not a descendant of the exact Model 3C predecessor.")

    tracked_delta = {
        line.strip()
        for line in git("diff", "--name-only", MODEL3C_COMMIT, "HEAD").splitlines()
        if line.strip()
    }
    untracked = {
        line.strip()
        for line in git("ls-files", "--others", "--exclude-standard").splitlines()
        if line.strip() and not line.startswith(IGNORED_UNTRACKED_PREFIXES)
    }
    actual = tracked_delta | untracked
    if actual != EXPECTED:
        fail(
            "3D delta must contain exactly the six governed paths.\n"
            f"Expected: {sorted(EXPECTED)}\nActual: {sorted(actual)}"
        )

    path = ROOT / "MODEL3D_STATE_SPACE_CONTRACT.json"
    if not path.exists():
        fail("MODEL3D_STATE_SPACE_CONTRACT.json is missing.")
    contract = json.loads(path.read_text(encoding="utf-8"))

    if contract.get("model3c_base_commit") != MODEL3C_COMMIT:
        fail("3D contract does not pin the exact 3C predecessor.")
    if contract.get("input_contract", {}).get("required_series") != "GDPC1":
        fail("3D must remain a univariate real-GDP state-space workstream.")
    if contract.get("input_contract", {}).get("joint_complete_model3b_panel_required") is not False:
        fail("3D must not require the joint-complete multivariate panel.")

    spec = contract.get("state_space_specification", {})
    if spec.get("state_vector") != [
        "potential_log_output",
        "trend_growth",
        "output_gap",
        "output_gap_lag1",
    ]:
        fail("Unexpected 3D state vector.")
    if spec.get("measurement_error_variance") != 0.0:
        fail("3D observation identity must retain zero measurement error.")
    if spec.get("fixed_parameters", {}).get("sigma_potential") != 0.0:
        fail("3D must fix the direct potential-level shock standard deviation at zero.")
    if spec.get("estimated_parameters") != ["sigma_trend_growth", "sigma_gap", "phi1", "phi2"]:
        fail("Unexpected 3D estimated parameter vector.")
    if spec.get("positive_standard_deviations_required") is not True:
        fail("Positive state-innovation standard deviations must be required.")
    if spec.get("stationary_gap_ar2_required") is not True:
        fail("Stationary AR(2) gap dynamics must be required.")

    estimation = contract.get("estimation", {})
    if estimation.get("optimizer") != "powell":
        fail("3D governed optimizer must be Powell.")
    if estimation.get("boundary_pile_up_guard_required") is not True:
        fail("3D must retain the boundary pile-up guard.")

    output = contract.get("output_contract", {})
    if output.get("filtered_full_sample_parameters_estimates_required") is not True:
        fail("Full-sample-parameter filtered estimates are required.")
    if output.get("filtered_full_sample_parameters_strict_real_time") is not False:
        fail("Full-sample-parameter filtered estimates must not be strict real-time.")
    if output.get("strict_real_time_endpoint_estimation_deferred_to") != "3H":
        fail("Strict real-time endpoint estimation must be deferred to 3H.")
    if output.get("smoothed_revised_estimates_required") is not True:
        fail("Smoothed revised estimates are required.")
    if output.get("filtered_and_smoothed_must_be_separately_labelled") is not True:
        fail("Filtered and smoothed estimates must be separately labelled.")

    integration = contract.get("integration", {})
    for key in (
        "inflation_allowed",
        "unemployment_allowed",
        "model1_integration_allowed",
        "model2_forecast_integration_allowed",
    ):
        if integration.get(key) is not False:
            fail(f"{key} must remain false in 3D.")

    governance = contract.get("governance", {})
    for key in (
        "production_winner_frozen",
        "automatic_selection_allowed",
        "automatic_promotion_allowed",
        "predecessor_modification_allowed",
        "database_writes_allowed",
        "generative_ai_in_governed_core_allowed",
        "smoothed_estimate_may_masquerade_as_real_time",
        "filtered_full_sample_parameters_may_masquerade_as_real_time",
    ):
        if governance.get(key) is not False:
            fail(f"{key} must remain false in 3D.")

    if contract.get("bootstrap", {}).get("passing_3d_authorizes_only") != \
            "3E_multivariate_macroeconomic_slack":
        fail("Passing 3D must authorize only 3E.")

    print("Model 3D state-space verification: PASS")
    print("Model 3C base: dfcee48")
    print("Immutable Model 2 base: cda2498")
    print("3D delta paths: 6")
    print("State vector: smooth potential output, stochastic trend growth, AR(2) output gap")
    print("Estimate classes: filtered_full_sample_parameters, smoothed_revised")
    print("Production winner: none")
    print("Next authorized workstream: 3E multivariate macroeconomic slack")


if __name__ == "__main__":
    main()

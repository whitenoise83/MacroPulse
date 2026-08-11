from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2B_DATA_VINTAGE_AUDIT.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_MODEL2A_COMMIT = "4033a8f88fa5ffc0bb749ab17621ab6e82074ec6"
EXPECTED_PHASE3_TAG = "phase3-evaluation-v1.0.1"
EXPECTED_PHASE3_COMMIT = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"

EXPECTED_DELTA = {
    "MODEL2B_DATA_VINTAGE_AUDIT.json",
    "docs/MODEL2B_DATA_VINTAGE_ARCHITECTURE.md",
    "src/macropulse/bvar/__init__.py",
    "src/macropulse/bvar/data.py",
    "scripts/audit_model2b_vintages.py",
    "scripts/verify_model2b_data_vintage_scaffold.py",
    "tests/test_model2b_data_vintage.py",
    "scripts/verify_phase3_evaluation.py",
    "scripts/verify_phase3_release.py",
    ".github/workflows/model2-bvar-guard.yml",
}

def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()

def names(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }

def main() -> int:
    errors: list[str] = []
    try:
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")
        phase3 = git("rev-parse", EXPECTED_PHASE3_TAG + "^{commit}")
        if phase3 != EXPECTED_PHASE3_COMMIT:
            errors.append("Immutable Phase III release tag moved.")
        for ancestor in (EXPECTED_PHASE3_COMMIT, EXPECTED_MODEL2A_COMMIT):
            completed = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT, capture_output=True, text=True,
            )
            if completed.returncode != 0:
                errors.append("HEAD does not descend from " + ancestor)

        committed = names(git("diff", "--name-only", EXPECTED_MODEL2A_COMMIT + "..HEAD"))
        working = names(git("diff", "--name-only"))
        staged = names(git("diff", "--cached", "--name-only"))
        untracked = names(git("ls-files", "--others", "--exclude-standard"))
        observed = committed | working | staged | untracked

        bad = sorted(observed - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - observed)
        if bad:
            errors.append("Unexpected 2B.1 paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2B.1 paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2B.1":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2a_commit") != EXPECTED_MODEL2A_COMMIT:
            errors.append("Wrong Model 2A base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        maintenance = payload.get("release_guard_maintenance", {})
        if maintenance.get("paths") != [
            "scripts/verify_phase3_evaluation.py",
            "scripts/verify_phase3_release.py",
        ]:
            errors.append("Phase III release-guard maintenance paths changed.")
        for key in (
            "phase3_release_tag_may_move",
            "phase3_manifest_may_change",
            "phase3_evaluation_semantics_changed",
            "model_semantics_changed",
        ):
            if maintenance.get(key) is not False:
                errors.append("Release-guard maintenance boundary changed: " + key)

        ci = payload.get("ci_guard", {})
        if ci.get("workflow") != ".github/workflows/model2-bvar-guard.yml":
            errors.append("Model 2 CI workflow identity changed.")
        if ci.get("push_branch") != EXPECTED_BRANCH:
            errors.append("Model 2 CI push branch changed.")
        if ci.get("pull_request_branch") != EXPECTED_BRANCH:
            errors.append("Model 2 CI pull-request branch changed.")
        for key in (
            "full_repository_suite_required",
            "frozen_phase2_verifier_required",
            "frozen_model1d_verifier_required",
            "phase3_release_verifier_required",
            "model2b_verifier_required",
        ):
            if ci.get(key) is not True:
                errors.append("Model 2 CI requirement changed: " + key)
        if ci.get("production_authority") != "none":
            errors.append("Model 2 CI production authority must remain none.")

        rules = payload.get("rules", {})
        required_true = (
            "read_only_database_access",
            "historical_snapshots_only",
            "exact_as_of_date_identity_required",
            "no_latest_vintage_fallback",
            "no_future_observation_date",
            "incomplete_quarters_excluded",
            "joint_panel_requires_all_four_transformed_series",
            "unrate_is_quarter_end_not_quarter_average",
            "unrate_missing_intermediate_month_may_not_be_imputed",
            "current_quarter_model1_anchor_deferred",
            "audit_does_not_select_estimation_start",
            "audit_does_not_select_model_candidate",
            "model1d_prospective_outcomes_excluded",
        )
        for key in required_true:
            if rules.get(key) is not True:
                errors.append("Fail-closed 2B.1 rule changed: " + key)
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2B.1 data/vintage audit scaffold verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2B.1 data/vintage audit scaffold verification: PASS")
    print("Branch: " + EXPECTED_BRANCH)
    print("Model 2A base: " + EXPECTED_MODEL2A_COMMIT[:7])
    print("Expected delta paths: 10")
    print("Historical snapshots only: PASS")
    print("No latest-vintage fallback: PASS")
    print("UNRATE quarterly rule: quarter-end level")
    print("Phase III frozen-release guard maintenance: PASS")
    print("Model 2 CI guard contract: PASS")
    print("Model 1 current-quarter anchor: deferred")
    print("Production authority: none")
    print("Next: close 2B.1 after green Model 2 CI")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

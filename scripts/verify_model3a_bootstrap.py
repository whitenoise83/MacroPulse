from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "MODEL3_BOUNDARY.json"

EXPECTED_BRANCH = "model3-output-gap-development"
EXPECTED_BASE_TAG = "model2-bvar-v1.0.2"
EXPECTED_BASE_COMMIT = "cda24988e772cd2b96be612b7d455c54a06f44fa"

EXPECTED_DELTA = {
    "MACROPULSE_MODEL3_PLAN.md",
    "MODEL3_BOUNDARY.json",
    "docs/MODEL3A_SLACK_SPECIFICATION_CONTRACT.md",
    "scripts/verify_model3a_bootstrap.py",
    "tests/test_model3a_bootstrap_contract.py",
}

IGNORED_UNTRACKED_PREFIXES = (
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
    "reports/decision_intelligence_snapshots/",
    "data/backups/",
    "src/macropulse.egg-info/",
)

class VerificationError(RuntimeError):
    pass

def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True
    )
    if completed.returncode != 0:
        raise VerificationError(
            "git " + " ".join(args) + " failed:\n"
            + completed.stdout + completed.stderr
        )
    return completed.stdout.strip()

def path_set(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines() if line.strip()
    }

def governed_untracked() -> set[str]:
    result = set()
    for path in path_set(git("ls-files", "--others", "--exclude-standard")):
        if not any(path.startswith(prefix) for prefix in IGNORED_UNTRACKED_PREFIXES):
            result.add(path)
    return result

def verify_branch_and_base() -> list[str]:
    errors = []
    branch = git("branch", "--show-current")
    # Named branch is required during bootstrap development, but the frozen
    # ancestry contract below is what later descendants/tags should rely on.
    if branch and branch != EXPECTED_BRANCH:
        errors.append(
            "Model 3A bootstrap must run on " + EXPECTED_BRANCH
            + " or detached HEAD; found " + repr(branch) + "."
        )
    tag_commit = git("rev-parse", EXPECTED_BASE_TAG + "^{commit}")
    if tag_commit != EXPECTED_BASE_COMMIT:
        errors.append(
            "Frozen Model 3 base tag moved: expected "
            + EXPECTED_BASE_COMMIT + ", got " + tag_commit + "."
        )
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, "HEAD"],
        cwd=ROOT, capture_output=True, text=True
    )
    if completed.returncode != 0:
        errors.append("HEAD does not descend from immutable Model 2 v1.0.2.")
    return errors

def verify_change_isolation() -> list[str]:
    committed = path_set(git("diff", "--name-only", EXPECTED_BASE_COMMIT + "..HEAD"))
    working = path_set(git("diff", "--name-only"))
    staged = path_set(git("diff", "--cached", "--name-only"))
    observed = committed | working | staged | governed_untracked()
    bad = sorted(observed - EXPECTED_DELTA)
    missing = sorted(EXPECTED_DELTA - observed)
    errors = []
    if bad:
        errors.append("Paths outside Model 3A allowlist: " + ", ".join(bad))
    if missing:
        errors.append("Missing expected Model 3A paths: " + ", ".join(missing))
    return errors

def verify_boundary() -> list[str]:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    errors = []
    expected = {
        "roadmap_phase": "II",
        "model": "3",
        "model_name": "Potential Output & Macroeconomic Slack",
        "branch": EXPECTED_BRANCH,
        "base_release_tag": EXPECTED_BASE_TAG,
        "base_release_commit": EXPECTED_BASE_COMMIT,
        "status": "specification_bootstrap",
        "promotion_authority": "none",
        "frequency": "quarterly",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append("Boundary mismatch " + key + ": " + repr(payload.get(key)))

    governance = payload.get("governance", {})
    for key, value in governance.items():
        if key.startswith("model3_") and value is not False:
            errors.append("Fail-closed governance changed: " + key)

    rt = payload.get("real_time_contract", {})
    for key in (
        "pseudo_real_time_required",
        "information_set_cutoff_required",
        "vintage_identity_required",
        "no_look_ahead_required",
        "latest_revised_data_may_not_masquerade_as_real_time",
        "revised_or_smoothed_estimates_separately_labelled",
        "monitoring_is_not_adaptation",
    ):
        if rt.get(key) is not True:
            errors.append("Real-time contract not fail-closed: " + key)

    integration = payload.get("integration_contract", {})
    if integration.get("model2_forecasts_may_determine_current_or_historical_potential") is not False:
        errors.append("Model 2 circularity firewall changed.")
    if integration.get("model2_forecasts_may_retune_model3_current_or_historical_estimator") is not False:
        errors.append("Model 2 retuning firewall changed.")

    bootstrap = payload.get("bootstrap_contract", {})
    if bootstrap.get("predecessor_file_modification_allowed") is not False:
        errors.append("Predecessor modification authority changed.")
    if bootstrap.get("passing_3a_authorizes_only") != "3B_real_time_data_vintages":
        errors.append("3A authorization boundary changed.")
    return errors

def verify_files() -> list[str]:
    return [
        "Missing Model 3A file: " + path
        for path in sorted(EXPECTED_DELTA)
        if not (ROOT / path).is_file()
    ]

def main() -> int:
    errors = []
    try:
        errors += verify_branch_and_base()
        errors += verify_change_isolation()
        errors += verify_files()
        errors += verify_boundary()
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 3A bootstrap verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 3A bootstrap verification: PASS")
    print("Base: " + EXPECTED_BASE_TAG + " -> " + EXPECTED_BASE_COMMIT[:7])
    print("Branch contract: " + EXPECTED_BRANCH)
    print("Bootstrap delta paths: " + str(len(EXPECTED_DELTA)))
    print("Predecessor modifications: none")
    print("Next authorized workstream: 3B real-time data/vintages")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

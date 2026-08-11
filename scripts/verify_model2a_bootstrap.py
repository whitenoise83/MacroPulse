from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "MODEL2_BOUNDARY.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_BASE_TAG = "phase3-evaluation-v1.0.1"
EXPECTED_BASE_COMMIT = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"

EXPECTED_DELTA = {
    "MACROPULSE_MODEL2_PLAN.md",
    "MODEL2_BOUNDARY.json",
    "docs/MODEL2A_BVAR_SPECIFICATION_CONTRACT.md",
    "scripts/verify_model2a_bootstrap.py",
    "tests/test_model2a_bootstrap_contract.py",
    "tests/test_phase3_bootstrap_contract.py",
}

REQUIRED_MODEL2_FILES = EXPECTED_DELTA - {"tests/test_phase3_bootstrap_contract.py"}


class VerificationError(RuntimeError):
    pass


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VerificationError(
            "git " + " ".join(args) + " failed:\n"
            + completed.stdout
            + completed.stderr
        )
    return completed.stdout.strip()


def path_set(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def verify_branch_and_base() -> list[str]:
    errors: list[str] = []

    branch = git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        errors.append(
            "Model 2A must run on " + EXPECTED_BRANCH + "; found " + repr(branch) + "."
        )

    tag_commit = git("rev-parse", EXPECTED_BASE_TAG + "^{commit}")
    if tag_commit != EXPECTED_BASE_COMMIT:
        errors.append(
            "Frozen Model 2 base tag moved: expected "
            + EXPECTED_BASE_COMMIT + ", got " + tag_commit + "."
        )

    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_BASE_COMMIT, "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        errors.append(
            "HEAD does not descend from the immutable Phase III v1.0.1 release."
        )

    return errors


def verify_change_isolation() -> list[str]:
    committed = path_set(
        git("diff", "--name-only", EXPECTED_BASE_COMMIT + "..HEAD")
    )
    working = path_set(git("diff", "--name-only"))
    staged = path_set(git("diff", "--cached", "--name-only"))
    untracked = path_set(git("ls-files", "--others", "--exclude-standard"))

    observed = committed | working | staged | untracked
    bad = sorted(observed - EXPECTED_DELTA)
    missing = sorted(EXPECTED_DELTA - observed)

    errors: list[str] = []
    if bad:
        errors.append(
            "Paths outside the Model 2A bootstrap/release-guard allowlist: "
            + ", ".join(bad)
        )
    if missing:
        errors.append(
            "Missing expected Model 2A delta paths: " + ", ".join(missing)
        )
    return errors


def verify_boundary() -> list[str]:
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    errors: list[str] = []

    expected = {
        "roadmap_phase": "II",
        "model": "2",
        "model_name": "Bayesian VAR Forecasting & Scenarios",
        "branch": EXPECTED_BRANCH,
        "base_release_tag": EXPECTED_BASE_TAG,
        "base_release_commit": EXPECTED_BASE_COMMIT,
        "status": "specification_bootstrap",
        "promotion_authority": "none",
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append("Boundary mismatch " + key + ": " + repr(payload.get(key)))

    governance = payload.get("governance", {})
    for key, value in governance.items():
        if key.startswith("model2_") or key.startswith("scenario_"):
            if value is not False:
                errors.append("Fail-closed governance changed: " + key)

    maintenance = payload.get("bootstrap_release_guard_maintenance", {})
    if maintenance.get("allowed_paths") != ["tests/test_phase3_bootstrap_contract.py"]:
        errors.append("Release-guard maintenance allowlist changed.")
    if maintenance.get("phase3_release_tag_may_move") is not False:
        errors.append("Phase III release tag must remain immutable.")
    if maintenance.get("phase3_evaluation_semantics_changed") is not False:
        errors.append("Phase III evaluation semantics must remain unchanged.")
    if maintenance.get("model_semantics_changed") is not False:
        errors.append("Model semantics must remain unchanged.")

    forecast = payload.get("forecast_contract", {})
    if forecast.get("forecast_horizons_quarters") != [1, 2, 4, 8]:
        errors.append("Forecast horizons changed.")
    for key in (
        "pseudo_real_time_required",
        "outcome_vintage_must_be_explicit",
        "first_release_default_where_defined",
        "revised_outcomes_must_be_separately_labelled",
        "no_look_ahead_required",
    ):
        if forecast.get(key) is not True:
            errors.append("Forecast contract changed: " + key)

    spec = payload.get("initial_bvar_specification", {})
    if spec.get("lag_candidates") != [2, 4]:
        errors.append("BVAR lag candidate grid changed.")
    if spec.get("overall_shrinkage_candidates") != [0.1, 0.2, 0.4]:
        errors.append("BVAR shrinkage candidate grid changed.")
    if spec.get("prospective_adaptation") is not False:
        errors.append("Prospective adaptation must remain disabled.")

    return errors


def verify_required_files() -> list[str]:
    missing = [
        path for path in sorted(REQUIRED_MODEL2_FILES)
        if not (ROOT / path).is_file()
    ]
    if not (ROOT / "tests/test_phase3_bootstrap_contract.py").is_file():
        missing.append("tests/test_phase3_bootstrap_contract.py")
    return [] if not missing else ["Missing files: " + ", ".join(missing)]


def verify_frozen_boundaries() -> list[str]:
    errors: list[str] = []
    commands = [
        (
            ["python", "scripts/verify_phase2_release.py", "--require-tag"],
            "Phase II platform",
        ),
        (
            ["python", "scripts/verify_model1d_v038_release.py", "--require-tags"],
            "Model 1D",
        ),
    ]
    for command, label in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            errors.append(
                label + " verifier failed:\n"
                + completed.stdout
                + completed.stderr
            )
    return errors


def main() -> int:
    errors: list[str] = []
    try:
        errors += verify_branch_and_base()
        errors += verify_change_isolation()
        errors += verify_boundary()
        errors += verify_required_files()
        errors += verify_frozen_boundaries()
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2A BVAR specification bootstrap verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2A BVAR specification bootstrap verification: PASS")
    print("Branch: " + EXPECTED_BRANCH)
    print("Frozen base: " + EXPECTED_BASE_TAG + " -> " + EXPECTED_BASE_COMMIT[:7])
    print("Expected delta paths: 6")
    print("Phase III release-guard maintenance: PASS")
    print("Initial system: GDP growth, core PCE inflation, unemployment, policy rate")
    print("Prior: NIW with Minnesota-style shrinkage; lags 2/4; lambda 0.1/0.2/0.4")
    print("Pseudo-real-time / Model 1 isolation: PASS")
    print("Promotion authority: none")
    print("Next authorized workstream: Model 2B data/vintage architecture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

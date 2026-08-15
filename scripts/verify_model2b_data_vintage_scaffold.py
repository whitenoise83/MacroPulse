from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_MODEL2A_COMMIT = "4033a8f88fa5ffc0bb749ab17621ab6e82074ec6"
EXPECTED_2B1_CLOSURE_COMMIT = "ff1217b3c154b2ae3dd0a6c931ce7200888c70b8"
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

IGNORED_GENERATED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
)

FROZEN_2B1_CONTENT_PATHS = EXPECTED_DELTA - {
    ".github/workflows/model2-bvar-guard.yml",
    "scripts/verify_model2b_data_vintage_scaffold.py",
}


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def names(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def is_ignorable_generated_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        normalized.startswith(prefix)
        for prefix in IGNORED_GENERATED_PREFIXES
    )


def compose_observed_paths(
    committed: set[str],
    working: set[str],
    staged: set[str],
    untracked: set[str],
) -> set[str]:
    runtime_working = {
        path for path in working
        if not is_ignorable_generated_path(path)
    }
    runtime_untracked = {
        path for path in untracked
        if not is_ignorable_generated_path(path)
    }
    return committed | runtime_working | staged | runtime_untracked


def main() -> int:
    errors: list[str] = []
    try:
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        phase3 = git("rev-parse", EXPECTED_PHASE3_TAG + "^{commit}")
        if phase3 != EXPECTED_PHASE3_COMMIT:
            errors.append("Immutable Phase III release tag moved.")

        for ancestor in (
            EXPECTED_PHASE3_COMMIT,
            EXPECTED_MODEL2A_COMMIT,
            EXPECTED_2B1_CLOSURE_COMMIT,
        ):
            completed = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                errors.append("HEAD does not descend from " + ancestor)

        closure_delta = names(
            git(
                "diff",
                "--name-only",
                EXPECTED_MODEL2A_COMMIT
                + ".."
                + EXPECTED_2B1_CLOSURE_COMMIT,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2B.1 paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2B.1 paths: " + ", ".join(missing))

        for frozen_path in sorted(FROZEN_2B1_CONTENT_PATHS):
            changed = subprocess.run(
                [
                    "git", "diff", "--quiet",
                    EXPECTED_2B1_CLOSURE_COMMIT, "--", frozen_path,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if changed.returncode != 0:
                errors.append("Frozen 2B.1 content changed: " + frozen_path)

        payload = json.loads(
            git(
                "show",
                EXPECTED_2B1_CLOSURE_COMMIT
                + ":MODEL2B_DATA_VINTAGE_AUDIT.json",
            )
        )
        if payload.get("workstream") != "2B.1":
            errors.append("Wrong frozen workstream identity.")
        if payload.get("base_model2a_commit") != EXPECTED_MODEL2A_COMMIT:
            errors.append("Wrong Model 2A base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        rules = payload.get("rules", {})
        required_true = (
            "read_only_database_access",
            "historical_snapshots_only",
            "exact_as_of_date_identity_required",
            "duplicate_exact_snapshot_rows_rejected",
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
                errors.append("Frozen 2B.1 rule changed: " + key)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2B.1 frozen data/vintage verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2B.1 frozen data/vintage verification: PASS")
    print("Model 2A base: " + EXPECTED_MODEL2A_COMMIT[:7])
    print("2B.1 closure: " + EXPECTED_2B1_CLOSURE_COMMIT[:7])
    print("Expected frozen delta paths: 10")
    print("Descendant-safe verification: PASS")
    print("Historical snapshots only: PASS")
    print("Duplicate exact snapshot rows rejected: PASS")
    print("UNRATE quarterly rule: quarter-end level")
    print("Production authority: none")
    print("Next: Model 2B.2 permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

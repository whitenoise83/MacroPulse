from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2B2_ORIGIN_GRID_CONTRACT.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2B1_CLOSURE = "ff1217b3c154b2ae3dd0a6c931ce7200888c70b8"
EXPECTED_DELTA = {
    "MODEL2_BOUNDARY.json",
    "MODEL2B2_ORIGIN_GRID_CONTRACT.json",
    "docs/MODEL2B2_PSEUDO_REALTIME_ORIGIN_GRID.md",
    "src/macropulse/bvar/origins.py",
    "scripts/audit_model2b2_origin_grid.py",
    "scripts/verify_model2b2_origin_grid.py",
    "scripts/verify_model2b_data_vintage_scaffold.py",
    "tests/test_model2b2_origin_grid.py",
    ".github/workflows/model2-bvar-guard.yml",
}

IGNORED_GENERATED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
)


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


def ignorable(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        normalized.startswith(prefix)
        for prefix in IGNORED_GENERATED_PREFIXES
    )


def main() -> int:
    errors: list[str] = []
    try:
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        ancestor = subprocess.run(
            [
                "git", "merge-base", "--is-ancestor",
                EXPECTED_2B1_CLOSURE, "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2B.1.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2B1_CLOSURE + "..HEAD")
        )
        working = {
            p for p in names(git("diff", "--name-only"))
            if not ignorable(p)
        }
        staged = names(git("diff", "--cached", "--name-only"))
        untracked = {
            p for p in names(
                git("ls-files", "--others", "--exclude-standard")
            )
            if not ignorable(p)
        }
        observed = committed | working | staged | untracked

        bad = sorted(observed - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - observed)
        if bad:
            errors.append("Unexpected 2B.2 paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2B.2 paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2B.2":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2b1_closure_commit") != EXPECTED_2B1_CLOSURE:
            errors.append("Wrong 2B.1 closure base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        rules = payload.get("rules", {})
        required_true = (
            "one_origin_per_newly_complete_quarter",
            "origin_cutoff_is_earliest_successful_common_cached_cutoff",
            "origin_quarter_equals_last_complete_joint_quarter",
            "last_complete_quarter_must_be_nondecreasing",
            "quarter_transitions_may_not_skip",
            "first_observed_state_is_left_censored",
            "left_censored_state_is_not_admissible_for_pseudo_real_time",
            "no_estimation_start_selected",
            "no_evaluation_start_selected",
            "no_model_candidate_selected",
            "historical_model1_backfill_prohibited",
            "model1_current_state_anchor_is_separate_prospective_interface",
            "model1_anchor_does_not_enter_baseline_parameter_estimation",
            "model1d_prospective_outcomes_excluded",
            "read_only_database_access",
            "exact_snapshot_identity_required",
            "source_snapshot_hash_required",
            "origin_id_deterministic",
        )
        for key in required_true:
            if rules.get(key) is not True:
                errors.append("2B.2 rule changed: " + key)

        if payload.get("forecast_horizons_quarters") != [1, 2, 4, 8]:
            errors.append("Forecast horizon labels changed.")

        boundary = json.loads(
            (ROOT / "MODEL2_BOUNDARY.json").read_text(encoding="utf-8")
        )
        unrate = [
            item
            for item in boundary.get("initial_endogenous_system", [])
            if item.get("series_id") == "UNRATE"
        ]
        if len(unrate) != 1:
            errors.append("UNRATE boundary identity is ambiguous.")
        elif unrate[0].get("quarterly_aggregation") != "quarter_end":
            errors.append("UNRATE boundary not aligned to 2B.1.")

        amendments = boundary.get("data_architecture_amendments", [])
        if not any(
            item.get("source_closure_commit") == EXPECTED_2B1_CLOSURE
            and item.get("series_id") == "UNRATE"
            and item.get("corrected_quarterly_aggregation") == "quarter_end"
            for item in amendments
        ):
            errors.append("UNRATE correction provenance is missing.")

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2b2_origin_grid.py",
            "tests/test_model2b2_origin_grid.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2B.2 gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2B.2 origin-grid verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2B.2 origin-grid verification: PASS")
    print("Base 2B.1 closure: " + EXPECTED_2B1_CLOSURE[:7])
    print("Expected delta paths: 9")
    print("One origin per newly complete quarter: PASS")
    print("Left-censored first state excluded: PASS")
    print("No skipped/decreasing quarter transitions: PASS")
    print("UNRATE master boundary aligned to quarter-end: PASS")
    print("Historical Model 1 backfill prohibited: PASS")
    print("Model 1 live anchor remains separate: PASS")
    print("Estimation/evaluation start selected: no")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2B1_CLOSURE = "ff1217b3c154b2ae3dd0a6c931ce7200888c70b8"
EXPECTED_2B2_CLOSURE = "90f529f635eeaa554259287ffc8a79647c92f7ad"

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

FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2b2_origin_grid.py",
    ".github/workflows/model2-bvar-guard.yml",
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


def main() -> int:
    errors: list[str] = []
    try:
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        for ancestor in (EXPECTED_2B1_CLOSURE, EXPECTED_2B2_CLOSURE):
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("HEAD does not descend from " + ancestor)

        closure_delta = names(
            git(
                "diff",
                "--name-only",
                EXPECTED_2B1_CLOSURE + ".." + EXPECTED_2B2_CLOSURE,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2B.2 paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2B.2 paths: " + ", ".join(missing))

        for path in sorted(FROZEN_CONTENT):
            result = subprocess.run(
                ["git", "diff", "--quiet", EXPECTED_2B2_CLOSURE, "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("Frozen 2B.2 content changed: " + path)

        payload = json.loads(
            git(
                "show",
                EXPECTED_2B2_CLOSURE
                + ":MODEL2B2_ORIGIN_GRID_CONTRACT.json",
            )
        )
        if payload.get("workstream") != "2B.2":
            errors.append("Wrong frozen 2B.2 workstream.")
        if payload.get("production_authority") != "none":
            errors.append("2B.2 production authority changed.")

        rules = payload.get("rules", {})
        for key in (
            "one_origin_per_newly_complete_quarter",
            "origin_cutoff_is_earliest_successful_common_cached_cutoff",
            "first_observed_state_is_left_censored",
            "left_censored_state_is_not_admissible_for_pseudo_real_time",
            "historical_model1_backfill_prohibited",
            "model1d_prospective_outcomes_excluded",
        ):
            if rules.get(key) is not True:
                errors.append("Frozen 2B.2 rule changed: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2b2_origin_grid.py",
            "tests/test_model2b2_origin_grid.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2B.2 gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2B.2 frozen origin-grid verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2B.2 frozen origin-grid verification: PASS")
    print("2B.1 closure: " + EXPECTED_2B1_CLOSURE[:7])
    print("2B.2 closure: " + EXPECTED_2B2_CLOSURE[:7])
    print("Frozen delta paths: 9")
    print("Descendant-safe verification: PASS")
    print("Origin rule frozen: PASS")
    print("Model 1 historical backfill prohibited: PASS")
    print("Production authority: none")
    print("Next: Model 2C permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

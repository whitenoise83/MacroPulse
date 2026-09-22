from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2E_CLOSURE = "559c581f6155f16c275e4523d67a8479310bf337"
EXPECTED_2F_CLOSURE = "c63ee4df92dd372f883feea4fc86eabae79ab358"
EXPECTED_2F_CI_RUN = 35750342329

EXPECTED_DELTA = {
    "MODEL2F_SCENARIO_CONTRACT.json",
    "docs/MODEL2F_SCENARIOS.md",
    "src/macropulse/bvar/scenario.py",
    "scripts/smoke_model2f_scenarios.py",
    "scripts/verify_model2f_scenarios.py",
    "scripts/verify_model2e_irf_fevd.py",
    "tests/test_model2f_scenarios.py",
    ".github/workflows/model2-bvar-guard.yml",
}

FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2f_scenarios.py",
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

        for ancestor in (EXPECTED_2E_CLOSURE, EXPECTED_2F_CLOSURE):
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
                EXPECTED_2E_CLOSURE + ".." + EXPECTED_2F_CLOSURE,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2F paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2F paths: " + ", ".join(missing))

        for path in sorted(FROZEN_CONTENT):
            result = subprocess.run(
                ["git", "diff", "--quiet", EXPECTED_2F_CLOSURE, "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("Frozen 2F content changed: " + path)

        payload = json.loads(
            git(
                "show",
                EXPECTED_2F_CLOSURE + ":MODEL2F_SCENARIO_CONTRACT.json",
            )
        )
        if payload.get("workstream") != "2F":
            errors.append("Wrong frozen 2F workstream.")
        if payload.get("production_authority") != "none":
            errors.append("2F production authority changed.")

        scenario = payload.get("scenario", {})
        if scenario.get("type") != "deterministic_hard_path_constraints":
            errors.append("Frozen 2F scenario type changed.")
        if scenario.get("scenario_probability_computed") is not False:
            errors.append("Frozen 2F probability boundary changed.")
        if scenario.get("causal_claim") is not False:
            errors.append("Frozen 2F causal boundary changed.")

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2f_scenarios.py",
            "tests/test_model2f_scenarios.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2F gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2F frozen scenario verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2F frozen scenario verification: PASS")
    print("2E closure: " + EXPECTED_2E_CLOSURE[:7])
    print("2F closure: " + EXPECTED_2F_CLOSURE[:7])
    print("2F closure CI run: " + str(EXPECTED_2F_CI_RUN))
    print("Frozen delta paths: 8")
    print("Descendant-safe verification: PASS")
    print("Scenario probability: not computed")
    print("Causal interpretation: prohibited")
    print("Candidate selection/ranking in 2F: prohibited")
    print("Production authority: none")
    print("Next: Model 2G permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

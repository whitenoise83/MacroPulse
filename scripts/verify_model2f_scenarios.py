from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2F_SCENARIO_CONTRACT.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2E_CLOSURE = "559c581f6155f16c275e4523d67a8479310bf337"

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

IGNORED_PREFIXES = (
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
    return any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES)


def main() -> int:
    errors: list[str] = []

    try:
        if git("branch", "--show-current") != EXPECTED_BRANCH:
            errors.append("Wrong branch.")

        ancestor = subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                EXPECTED_2E_CLOSURE,
                "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2E.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2E_CLOSURE + "..HEAD")
        )
        working = {
            path
            for path in names(git("diff", "--name-only"))
            if not ignorable(path)
        }
        staged = names(git("diff", "--cached", "--name-only"))
        untracked = {
            path
            for path in names(
                git("ls-files", "--others", "--exclude-standard")
            )
            if not ignorable(path)
        }
        observed = committed | working | staged | untracked

        bad = sorted(observed - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - observed)
        if bad:
            errors.append("Unexpected 2F paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2F paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2F":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2e_closure_commit") != EXPECTED_2E_CLOSURE:
            errors.append("Wrong 2E closure base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        policy = payload.get("candidate_policy", {})
        if policy.get("all_six_model2c_candidates_retained") is not True:
            errors.append("2F candidate retention changed.")
        for key in (
            "candidate_selection_in_2f",
            "candidate_ranking_in_2f",
            "automatic_candidate_exclusion_in_2f",
        ):
            if policy.get(key) is not False:
                errors.append("2F candidate action changed: " + key)

        baseline = payload.get("baseline", {})
        if baseline.get("path_horizons_quarters") != list(range(1, 9)):
            errors.append("2F path horizons changed.")
        if baseline.get("standard_report_horizons_quarters") != [1, 2, 4, 8]:
            errors.append("2F report horizons changed.")
        if baseline.get("exact_estimation_panel_hash_required") is not True:
            errors.append("2F exact-panel identity rule changed.")

        scenario = payload.get("scenario", {})
        if scenario.get("type") != "deterministic_hard_path_constraints":
            errors.append("2F scenario type changed.")
        if scenario.get("scenario_probability_computed") is not False:
            errors.append("2F scenario probability boundary changed.")
        if scenario.get("bayesian_conditional_density_computed") is not False:
            errors.append("2F conditional-density boundary changed.")
        if scenario.get("causal_claim") is not False:
            errors.append("2F causal boundary changed.")
        if (
            scenario.get("duplicate_variable_horizon_constraints_rejected")
            is not True
        ):
            errors.append("2F duplicate-constraint rule changed.")

        interpretation = payload.get("interpretation", {})
        for key in (
            "no_probability_language",
            "no_causal_language",
            "structural_shock_identification_not_invoked",
        ):
            if interpretation.get(key) is not True:
                errors.append("2F interpretation boundary changed: " + key)

        governance = payload.get("governance", {})
        for key in (
            "no_candidate_selection",
            "no_candidate_ranking",
            "no_estimation_start_selection",
            "no_evaluation_start_selection",
            "no_model1_historical_backfill",
            "no_model1d_prospective_outcomes",
            "no_frozen_release_changes",
            "no_production_promotion",
            "no_scenario_probability_claims",
            "no_unidentified_causal_claims",
        ):
            if governance.get(key) is not True:
                errors.append("2F governance changed: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2f_scenarios.py",
            "tests/test_model2f_scenarios.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2F gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2F scenario verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2F scenario verification: PASS")
    print("Base 2E closure: " + EXPECTED_2E_CLOSURE[:7])
    print("Expected delta paths: 8")
    print("Scenario type: deterministic hard path constraints")
    print("Path horizons: 1-8 quarters")
    print("Standard report horizons: 1, 2, 4, 8")
    print("Six Model 2C candidates retained: PASS")
    print("Scenario probability: not computed")
    print("Bayesian conditional density: not computed")
    print("Causal interpretation: prohibited")
    print("Candidate selection/ranking in 2F: prohibited")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2C_CLOSURE = "b321e3f59ac7165cf71b1b3155712312b58af1a7"
EXPECTED_2D_CLOSURE = "a40c5f3f5426982f5d23781ad26467c97be501c8"
EXPECTED_2D_CI_RUN = 33891568448

EXPECTED_DELTA = {
    "MODEL2D_PROBABILISTIC_FORECAST_CONTRACT.json",
    "docs/MODEL2D_PROBABILISTIC_FORECASTS.md",
    "src/macropulse/bvar/probabilistic.py",
    "scripts/smoke_model2d_probabilistic.py",
    "scripts/verify_model2d_probabilistic.py",
    "scripts/verify_model2c_baseline_bvar.py",
    "tests/test_model2d_probabilistic.py",
    ".github/workflows/model2-bvar-guard.yml",
}

FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2d_probabilistic.py",
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

        for ancestor in (EXPECTED_2C_CLOSURE, EXPECTED_2D_CLOSURE):
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
                EXPECTED_2C_CLOSURE + ".." + EXPECTED_2D_CLOSURE,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2D paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2D paths: " + ", ".join(missing))

        for path in sorted(FROZEN_CONTENT):
            result = subprocess.run(
                ["git", "diff", "--quiet", EXPECTED_2D_CLOSURE, "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("Frozen 2D content changed: " + path)

        payload = json.loads(
            git(
                "show",
                EXPECTED_2D_CLOSURE
                + ":MODEL2D_PROBABILISTIC_FORECAST_CONTRACT.json",
            )
        )
        if payload.get("workstream") != "2D":
            errors.append("Wrong frozen 2D workstream.")
        if payload.get("production_authority") != "none":
            errors.append("2D production authority changed.")

        policy = payload.get("candidate_policy", {})
        if policy.get("all_six_model2c_candidates_retained") is not True:
            errors.append("Frozen 2D candidate retention changed.")
        for key in (
            "candidate_selection_in_2d",
            "candidate_ranking_in_2d",
            "automatic_candidate_exclusion_in_2d",
        ):
            if policy.get(key) is not False:
                errors.append("Frozen 2D candidate action changed: " + key)

        predictive = payload.get("posterior_predictive", {})
        for key in (
            "future_innovations_drawn",
            "one_parameter_draw_per_simulated_path",
            "parameter_uncertainty_included",
            "innovation_uncertainty_included",
            "recursive_multi_step_simulation",
        ):
            if predictive.get(key) is not True:
                errors.append("Frozen 2D predictive rule changed: " + key)

        if predictive.get("stability_truncation_or_rejection") is not False:
            errors.append("Frozen 2D stability boundary changed.")

        simulation = payload.get("simulation", {})
        if simulation.get("canonical_default_seed") != 20260904:
            errors.append("Frozen 2D seed changed.")
        if simulation.get("canonical_default_simulations") != 5000:
            errors.append("Frozen 2D simulation count changed.")

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2d_probabilistic.py",
            "tests/test_model2d_probabilistic.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2D gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2D frozen probabilistic verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2D frozen probabilistic verification: PASS")
    print("2C closure: " + EXPECTED_2C_CLOSURE[:7])
    print("2D closure: " + EXPECTED_2D_CLOSURE[:7])
    print("2D closure CI run: " + str(EXPECTED_2D_CI_RUN))
    print("Frozen delta paths: 8")
    print("Descendant-safe verification: PASS")
    print("Six-candidate retention frozen: PASS")
    print("Probabilistic simulation contract frozen: PASS")
    print("Candidate selection/ranking: prohibited")
    print("Production authority: none")
    print("Next: Model 2E permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

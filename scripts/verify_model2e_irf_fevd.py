from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2D_CLOSURE = "a40c5f3f5426982f5d23781ad26467c97be501c8"
EXPECTED_2E_CLOSURE = "559c581f6155f16c275e4523d67a8479310bf337"
EXPECTED_2E_CI_RUN = 35747825040

EXPECTED_DELTA = {
    "MODEL2E_IRF_FEVD_CONTRACT.json",
    "docs/MODEL2E_IRF_FEVD.md",
    "src/macropulse/bvar/structural.py",
    "scripts/smoke_model2e_irf_fevd.py",
    "scripts/verify_model2e_irf_fevd.py",
    "scripts/verify_model2d_probabilistic.py",
    "tests/test_model2e_irf_fevd.py",
    ".github/workflows/model2-bvar-guard.yml",
}

FROZEN_CONTENT = EXPECTED_DELTA - {
    "scripts/verify_model2e_irf_fevd.py",
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

        for ancestor in (EXPECTED_2D_CLOSURE, EXPECTED_2E_CLOSURE):
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
                EXPECTED_2D_CLOSURE + ".." + EXPECTED_2E_CLOSURE,
            )
        )
        bad = sorted(closure_delta - EXPECTED_DELTA)
        missing = sorted(EXPECTED_DELTA - closure_delta)
        if bad:
            errors.append("Unexpected frozen 2E paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing frozen 2E paths: " + ", ".join(missing))

        for path in sorted(FROZEN_CONTENT):
            result = subprocess.run(
                ["git", "diff", "--quiet", EXPECTED_2E_CLOSURE, "--", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                errors.append("Frozen 2E content changed: " + path)

        payload = json.loads(
            git(
                "show",
                EXPECTED_2E_CLOSURE + ":MODEL2E_IRF_FEVD_CONTRACT.json",
            )
        )
        if payload.get("workstream") != "2E":
            errors.append("Wrong frozen 2E workstream.")
        if payload.get("production_authority") != "none":
            errors.append("2E production authority changed.")

        policy = payload.get("candidate_policy", {})
        if policy.get("all_six_model2c_candidates_retained") is not True:
            errors.append("Frozen 2E candidate retention changed.")
        for key in (
            "candidate_selection_in_2e",
            "candidate_ranking_in_2e",
            "automatic_candidate_exclusion_in_2e",
        ):
            if policy.get(key) is not False:
                errors.append("Frozen 2E candidate action changed: " + key)

        identification = payload.get("identification", {})
        if identification.get("method") != "recursive_cholesky":
            errors.append("Frozen 2E identification method changed.")
        if identification.get("ordering") != [
            "real_gdp_growth",
            "core_pce_inflation",
            "unemployment_rate",
            "policy_rate",
        ]:
            errors.append("Frozen 2E recursive ordering changed.")

        irf = payload.get("irf", {})
        fevd = payload.get("fevd", {})
        if irf.get("reported_horizons_quarters") != [1, 4, 8, 12]:
            errors.append("Frozen 2E IRF horizons changed.")
        if fevd.get("reported_horizons_quarters") != [1, 4, 8, 12]:
            errors.append("Frozen 2E FEVD horizons changed.")

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2e_irf_fevd.py",
            "tests/test_model2e_irf_fevd.py",
        ):
            if token not in workflow:
                errors.append("Current CI lost frozen 2E gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2E frozen IRF/FEVD verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2E frozen IRF/FEVD verification: PASS")
    print("2D closure: " + EXPECTED_2D_CLOSURE[:7])
    print("2E closure: " + EXPECTED_2E_CLOSURE[:7])
    print("2E closure CI run: " + str(EXPECTED_2E_CI_RUN))
    print("Frozen delta paths: 8")
    print("Descendant-safe verification: PASS")
    print("Recursive identification frozen: PASS")
    print("IRF/FEVD horizons frozen: PASS")
    print("Candidate selection/ranking: prohibited")
    print("Production authority: none")
    print("Next: Model 2F permitted on descendants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

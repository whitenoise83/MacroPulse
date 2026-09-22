from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2E_IRF_FEVD_CONTRACT.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2D_CLOSURE = "a40c5f3f5426982f5d23781ad26467c97be501c8"

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
                EXPECTED_2D_CLOSURE,
                "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2D.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2D_CLOSURE + "..HEAD")
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
            errors.append("Unexpected 2E paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2E paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2E":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2d_closure_commit") != EXPECTED_2D_CLOSURE:
            errors.append("Wrong 2D closure base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        policy = payload.get("candidate_policy", {})
        if policy.get("all_six_model2c_candidates_retained") is not True:
            errors.append("2E candidate retention changed.")
        for key in (
            "candidate_selection_in_2e",
            "candidate_ranking_in_2e",
            "automatic_candidate_exclusion_in_2e",
        ):
            if policy.get(key) is not False:
                errors.append("2E candidate action changed: " + key)

        identification = payload.get("identification", {})
        if identification.get("method") != "recursive_cholesky":
            errors.append("2E identification method changed.")
        if identification.get("ordering") != [
            "real_gdp_growth",
            "core_pce_inflation",
            "unemployment_rate",
            "policy_rate",
        ]:
            errors.append("2E recursive ordering changed.")
        if identification.get("coefficient_representation") != "posterior_mean":
            errors.append("2E coefficient representation changed.")
        if (
            identification.get("covariance_representation")
            != "posterior_expected_residual_covariance"
        ):
            errors.append("2E covariance representation changed.")
        if (
            identification.get(
                "causal_interpretation_is_conditional_on_identification"
            )
            is not True
        ):
            errors.append("2E causal-interpretation boundary changed.")

        irf = payload.get("irf", {})
        fevd = payload.get("fevd", {})
        if irf.get("reported_horizons_quarters") != [1, 4, 8, 12]:
            errors.append("2E IRF horizons changed.")
        if fevd.get("reported_horizons_quarters") != [1, 4, 8, 12]:
            errors.append("2E FEVD horizons changed.")
        if fevd.get("shares_sum_to_one_by_response_and_horizon") is not True:
            errors.append("2E FEVD add-up rule changed.")
        if fevd.get("shares_bounded_zero_one") is not True:
            errors.append("2E FEVD bounds rule changed.")

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
            "no_unidentified_causal_claims",
        ):
            if governance.get(key) is not True:
                errors.append("2E governance changed: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2e_irf_fevd.py",
            "tests/test_model2e_irf_fevd.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2E gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2E IRF/FEVD verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2E IRF/FEVD verification: PASS")
    print("Base 2D closure: " + EXPECTED_2D_CLOSURE[:7])
    print("Expected delta paths: 8")
    print("Identification: recursive Cholesky")
    print(
        "Ordering: GDP growth -> core PCE inflation -> "
        "unemployment -> policy rate"
    )
    print("IRF horizons: 1, 4, 8, 12")
    print("FEVD horizons: 1, 4, 8, 12")
    print("FEVD add-up/bounds rules: frozen")
    print("Six Model 2C candidates retained: PASS")
    print("Candidate selection/ranking in 2E: prohibited")
    print("Causal interpretation: conditional on identification")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

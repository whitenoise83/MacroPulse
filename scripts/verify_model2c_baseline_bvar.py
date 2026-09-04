from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2C_BASELINE_BVAR_CONTRACT.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2B2_CLOSURE = "90f529f635eeaa554259287ffc8a79647c92f7ad"
EXPECTED_DELTA = {
    "MODEL2C_BASELINE_BVAR_CONTRACT.json",
    "docs/MODEL2C_BASELINE_BVAR.md",
    "src/macropulse/bvar/model.py",
    "scripts/smoke_model2c_bvar.py",
    "scripts/verify_model2c_baseline_bvar.py",
    "scripts/verify_model2b2_origin_grid.py",
    "tests/test_model2c_baseline_bvar.py",
    "src/macropulse/models/baseline.py",
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
                "git", "merge-base", "--is-ancestor",
                EXPECTED_2B2_CLOSURE, "HEAD",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2B.2.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2B2_CLOSURE + "..HEAD")
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
            errors.append("Unexpected 2C paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2C paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2C":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2b2_closure_commit") != EXPECTED_2B2_CLOSURE:
            errors.append("Wrong 2B.2 closure base.")
        if payload.get("production_authority") != "none":
            errors.append("Production authority must remain none.")

        grid = payload.get("candidate_grid", {})
        if grid.get("lags") != [2, 4]:
            errors.append("Lag grid changed.")
        if grid.get("overall_shrinkage") != [0.1, 0.2, 0.4]:
            errors.append("Shrinkage grid changed.")
        if grid.get("candidate_count") != 6:
            errors.append("Candidate count changed.")
        if grid.get("selection_in_2c") is not False:
            errors.append("2C may not select a candidate.")
        if grid.get("ranking_in_2c") is not False:
            errors.append("2C may not rank candidates.")

        prior = payload.get("prior", {})
        if prior.get("family") != "matrix_normal_inverse_wishart":
            errors.append("Prior family changed.")
        if prior.get("style") != "minnesota_style_conjugate":
            errors.append("Prior style changed.")

        forecast = payload.get("forecast", {})
        if forecast.get("horizons_quarters") != [1, 2, 4, 8]:
            errors.append("Forecast horizons changed.")
        if forecast.get("method_2c") != "recursive_posterior_mean_point_forecast":
            errors.append("2C forecast method changed.")
        for key in (
            "posterior_predictive_density_deferred_to_2d",
            "intervals_deferred_to_2d",
            "simulation_seed_deferred_to_2d",
        ):
            if forecast.get(key) is not True:
                errors.append("2D boundary changed: " + key)

        maintenance = payload.get(
            "dependency_compatibility_maintenance", {}
        )
        if maintenance.get("paths") != [
            "src/macropulse/models/baseline.py"
        ]:
            errors.append("Dependency compatibility path changed.")
        for key in (
            "model1_forecast_semantics_changed",
            "model2_bvar_semantics_changed",
            "frozen_release_tags_changed",
            "production_authority_changed",
        ):
            if maintenance.get(key) is not False:
                errors.append(
                    "Dependency compatibility boundary changed: " + key
                )

        baseline_text = (
            ROOT / "src" / "macropulse" / "models" / "baseline.py"
        ).read_text(encoding="utf-8")
        if "old_names=" in baseline_text:
            errors.append(
                "Deprecated statsmodels AutoReg old_names keyword remains."
            )

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
        ):
            if governance.get(key) is not True:
                errors.append("2C governance changed: " + key)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2c_baseline_bvar.py",
            "tests/test_model2c_baseline_bvar.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2C gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2C baseline BVAR verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2C baseline BVAR verification: PASS")
    print("Base 2B.2 closure: " + EXPECTED_2B2_CLOSURE[:7])
    print("Expected delta paths: 9")
    print("statsmodels 0.15 AutoReg compatibility: PASS")
    print("Candidate grid: 2 lags x 3 shrinkage values = 6")
    print("Candidate selection/ranking in 2C: prohibited")
    print("Prior: conjugate NIW with Minnesota-style shrinkage")
    print("Forecast: posterior-mean point forecast only")
    print("Density/interval simulation: deferred to 2D")
    print("Production authority: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

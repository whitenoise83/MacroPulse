from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "MODEL2H_RELEASE_CANDIDATE_CONTRACT.json"
EVIDENCE = ROOT / "MODEL2G_SELECTION_EVIDENCE.json"

EXPECTED_BRANCH = "model2-bvar-development"
EXPECTED_2G_CLOSURE = "ad196fb5d9a2d0d2c9113ea94d1363573c0c3b56"
EXPECTED_2G_CI_RUN = 35754237381
EXPECTED_SELECTED_ID = "a69878bf644615c5"
EXPECTED_LAGS = 2
EXPECTED_SHRINKAGE = 0.1
EXPECTED_EVIDENCE_PAYLOAD_HASH = "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
EXPECTED_TAG = "model2-bvar-v1.0.0"

EXPECTED_DELTA = {
    "MODEL2H_RELEASE_CANDIDATE_CONTRACT.json",
    "docs/MODEL2H_PRODUCTION_HARDENING.md",
    "src/macropulse/bvar/production.py",
    "scripts/smoke_model2h_production.py",
    "scripts/verify_model2h_production.py",
    "scripts/verify_model2g_evaluation.py",
    "tests/test_model2h_production.py",
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
            ["git", "merge-base", "--is-ancestor", EXPECTED_2G_CLOSURE, "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if ancestor.returncode != 0:
            errors.append("HEAD does not descend from closed Model 2G.")

        committed = names(
            git("diff", "--name-only", EXPECTED_2G_CLOSURE + "..HEAD")
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
            errors.append("Unexpected 2H paths: " + ", ".join(bad))
        if missing:
            errors.append("Missing 2H paths: " + ", ".join(missing))

        payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
        if payload.get("workstream") != "2H":
            errors.append("Wrong workstream identity.")
        if payload.get("base_model2g_closure_commit") != EXPECTED_2G_CLOSURE:
            errors.append("Wrong 2G closure base.")
        if payload.get("base_model2g_closure_ci_run_id") != EXPECTED_2G_CI_RUN:
            errors.append("Wrong 2G closure CI evidence.")
        if payload.get("production_authority") != "none_until_release_tag":
            errors.append("2H release-candidate authority boundary changed.")

        release = payload.get("release", {})
        if release.get("version") != "1.0.0":
            errors.append("Model 2 planned release version changed.")
        if release.get("planned_tag") != EXPECTED_TAG:
            errors.append("Model 2 planned release tag changed.")
        if release.get("tag_not_created_by_bootstrap") is not True:
            errors.append("2H bootstrap must not create release tag.")
        if release.get("release_requires_green_source_ci") is not True:
            errors.append("2H release source-CI gate changed.")
        if release.get("release_requires_separate_release_metadata_patch") is not True:
            errors.append("2H release metadata boundary changed.")

        selected = payload.get("selected_specification", {})
        if selected.get("candidate_id") != EXPECTED_SELECTED_ID:
            errors.append("2H selected candidate ID changed.")
        if selected.get("lags") != EXPECTED_LAGS:
            errors.append("2H selected lag order changed.")
        if abs(float(selected.get("shrinkage", -1.0)) - EXPECTED_SHRINKAGE) > 1e-12:
            errors.append("2H selected shrinkage changed.")
        if selected.get("selection_evidence_payload_hash") != EXPECTED_EVIDENCE_PAYLOAD_HASH:
            errors.append("2H selection evidence identity changed.")
        if selected.get("prospective_retuning_allowed") is not False:
            errors.append("2H prospective retuning boundary changed.")
        if selected.get("automatic_switching_allowed") is not False:
            errors.append("2H automatic switching boundary changed.")

        forecast = payload.get("forecast_interface", {})
        if forecast.get("horizons_quarters") != [1, 2, 4, 8]:
            errors.append("2H forecast horizons changed.")
        if forecast.get("default_simulations") != 5000:
            errors.append("2H default simulation count changed.")
        if forecast.get("default_seed") != 20260904:
            errors.append("2H default simulation seed changed.")
        if forecast.get("scenario_analysis_automatic") is not False:
            errors.append("2H must not run scenarios automatically.")
        if forecast.get("exact_panel_hash_enforced") is not True:
            errors.append("2H exact-panel lineage changed.")
        if forecast.get("future_observation_rows_rejected") is not True:
            errors.append("2H future-observation guard changed.")
        if forecast.get("deterministic_output_fingerprint") is not True:
            errors.append("2H output-fingerprint boundary changed.")

        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        if evidence.get("evidence_payload_hash") != EXPECTED_EVIDENCE_PAYLOAD_HASH:
            errors.append("Frozen 2G selection evidence changed.")
        frozen = evidence.get("selected_candidate", {})
        if frozen.get("candidate_id") != EXPECTED_SELECTED_ID:
            errors.append("2G/2H selected candidate ID mismatch.")
        if frozen.get("lags") != EXPECTED_LAGS:
            errors.append("2G/2H selected lag mismatch.")
        if abs(float(frozen.get("shrinkage", -1.0)) - EXPECTED_SHRINKAGE) > 1e-12:
            errors.append("2G/2H selected shrinkage mismatch.")

        production = (
            ROOT / "src" / "macropulse" / "bvar" / "production.py"
        ).read_text(encoding="utf-8")
        for token in (
            'SELECTED_CANDIDATE_ID = "a69878bf644615c5"',
            "SELECTED_LAGS = 2",
            "SELECTED_SHRINKAGE = 0.1",
            'PLANNED_RELEASE_TAG = "model2-bvar-v1.0.0"',
            "def run_model2_forecast(",
            "build_complete_quarter_panel",
            "simulate_posterior_predictive",
            "structural_analysis",
        ):
            if token not in production:
                errors.append("2H production interface missing token: " + token)

        workflow = (
            ROOT / ".github" / "workflows" / "model2-bvar-guard.yml"
        ).read_text(encoding="utf-8")
        for token in (
            "python scripts/verify_model2h_production.py",
            "tests/test_model2h_production.py",
        ):
            if token not in workflow:
                errors.append("Model 2 CI missing 2H gate: " + token)

    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2H production hardening verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2H production hardening verification: PASS")
    print("Base 2G closure: " + EXPECTED_2G_CLOSURE[:7])
    print("Base 2G CI run: " + str(EXPECTED_2G_CI_RUN))
    print("Expected delta paths: 8")
    print("Frozen candidate: p=2 lambda=0.1 id=" + EXPECTED_SELECTED_ID)
    print("Forecast horizons: 1, 2, 4, 8")
    print("Default posterior simulations: 5000")
    print("Default seed: 20260904")
    print("Pure forecast interface/database writes: none")
    print("Candidate reselection/retuning: prohibited")
    print("Planned release tag: " + EXPECTED_TAG)
    print("Production authority before release tag: none")
    print("Next: exact 2H source CI, then release metadata/tag patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

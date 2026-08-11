from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

EXPECTED_BRANCH = "phase3-evaluation-development"
EXPECTED_PHASE2_TAG = "phase2-platform-v1.0.0"
EXPECTED_PHASE2_COMMIT = "43395d889a76453706259a5095bd718337b55851"

ALLOWED_EXACT_PHASE3_PATHS = {
    ".gitignore", "app.py", "MACROPULSE_PHASE3_PLAN.md", "PHASE3_BOUNDARY.json",
    "PHASE3_RELEASE.json", "MANIFEST_PHASE3_v1.0.0.txt",
    "README_PHASE3_v1.0.0.md", "VALIDATION_PHASE3_v1.0.0.txt",
    "MANIFEST_PHASE3_v1.0.1.txt", "README_PHASE3_v1.0.1.md",
    "VALIDATION_PHASE3_v1.0.1.txt",
    "ui/evaluation_dashboard.py",
}
ALLOWED_PHASE3_PREFIXES = (
    ".github/workflows/phase3-", "docs/PHASE3",
    "src/macropulse/evaluation/", "tests/test_phase3",
)
ALLOWED_PHASE3_SCRIPTS = {
    "scripts/export_decision_intelligence_snapshot.py",
    "scripts/refresh_phase3_outcome_snapshots.py",
    "scripts/report_decision_intelligence.py",
    "scripts/report_forecast_evaluation.py",
    "scripts/report_forecast_performance.py",
    "scripts/report_forecast_revisions.py",
    "scripts/verify_phase3_evaluation.py",
    "scripts/verify_phase3_release.py",
}
REQUIRED_PHASE3_FILES = (
    "MACROPULSE_PHASE3_PLAN.md", "PHASE3_BOUNDARY.json",
    "docs/PHASE3_ARCHITECTURE.md",
    "docs/PHASE3B_EVALUATION_LEDGER_CONTRACT.md",
    "docs/PHASE3C_ACCURACY_CALIBRATION_DRIFT_CONTRACT.md",
    "docs/PHASE3D_REVISION_RELEASE_IMPACT_CONTRACT.md",
    "docs/PHASE3E_DECISION_INTELLIGENCE_CONTRACT.md",
    "docs/PHASE3_OPERATIONAL_RUNBOOK.md",
    "src/macropulse/evaluation/ledger.py",
    "src/macropulse/evaluation/performance.py",
    "src/macropulse/evaluation/revisions.py",
    "src/macropulse/evaluation/decision.py",
    "src/macropulse/evaluation/dashboard.py",
    "scripts/report_forecast_evaluation.py",
    "scripts/report_forecast_performance.py",
    "scripts/report_forecast_revisions.py",
    "scripts/report_decision_intelligence.py",
    "scripts/export_decision_intelligence_snapshot.py",
    "ui/evaluation_dashboard.py",
    ".github/workflows/phase3-evaluation-guard.yml",
)

class Phase3VerificationError(RuntimeError):
    pass

def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if completed.returncode != 0:
        raise Phase3VerificationError(
            f"git {' '.join(args)} failed:\n" + completed.stdout + completed.stderr
        )
    return completed.stdout.strip()

def verify_boundary(root: Path) -> list[str]:
    path = root / "PHASE3_BOUNDARY.json"
    if not path.is_file():
        return ["PHASE3_BOUNDARY.json is missing."]
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("phase") != "III":
        errors.append("Phase III identity changed.")
    if payload.get("branch") != EXPECTED_BRANCH:
        errors.append("Phase III branch identity changed.")
    if payload.get("base_release_tag") != EXPECTED_PHASE2_TAG:
        errors.append("Phase III Phase II base tag changed.")
    if payload.get("base_release_commit") != EXPECTED_PHASE2_COMMIT:
        errors.append("Phase III Phase II base commit changed.")
    false_boundaries = (
        "phase3_core_may_use_generative_ai",
        "phase3_may_automatically_promote_or_demote_models",
        "phase3_may_backfill_model1d",
        "phase3_may_change_model_specifications",
        "phase3_may_move_model1d_release_tags",
        "phase3_may_move_phase2_release_tag",
        "phase3_may_mutate_governed_forecasts",
        "phase3_may_tune_model1d_on_prospective_outcomes",
    )
    for key in false_boundaries:
        if payload.get(key) is not False:
            errors.append(f"Phase III fail-closed boundary changed: {key}")
    rules = payload.get("evaluation_rules", {})
    true_rules = (
        "first_release_default_where_defined",
        "monitoring_is_not_adaptation",
        "no_look_ahead_required",
        "outcome_vintage_must_be_explicit",
        "release_impact_is_descriptive_unless_causal_design_is_governed",
        "revised_outcomes_separately_labelled",
    )
    for key in true_rules:
        if rules.get(key) is not True:
            errors.append(f"Phase III evaluation rule changed: {key}")
    suite = payload.get("model_suite", {})
    for component in ("1A", "1B", "1C"):
        item = suite.get(component, {})
        if item.get("status") != "production" or item.get("version") != "1.0.0":
            errors.append(f"Phase III production identity changed for {component}.")
    model1d = suite.get("1D", {})
    if model1d.get("status") != "development":
        errors.append("Model 1D status changed.")
    if model1d.get("version") != "0.3.8":
        errors.append("Model 1D version changed.")
    if model1d.get("mode") != "prospective_shadow":
        errors.append("Model 1D mode changed.")
    if model1d.get("promotion_authority") != "none":
        errors.append("Model 1D promotion authority changed.")
    expected_workstreams = {
        "3A_bootstrap_evidence_contract",
        "3B_production_forecast_evaluation_ledger",
        "3C_accuracy_calibration_drift",
        "3D_revision_release_impact",
        "3E_decision_intelligence_presentation",
        "3F_operational_hardening_release",
    }
    if set(payload.get("workstreams", [])) != expected_workstreams:
        errors.append("Phase III workstream identity changed.")
    return errors

def verify_phase2_ancestry(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_PHASE2_COMMIT, "HEAD"],
        cwd=root, capture_output=True, text=True,
    )
    return [] if completed.returncode == 0 else [
        "Phase III HEAD does not descend from the immutable Phase II release commit."
    ]

def _path_allowed(relative: str) -> bool:
    if relative in ALLOWED_EXACT_PHASE3_PATHS or relative in ALLOWED_PHASE3_SCRIPTS:
        return True
    return any(relative.startswith(prefix) for prefix in ALLOWED_PHASE3_PREFIXES)

def verify_phase3_change_isolation(root: Path) -> list[str]:
    try:
        output = _git(root, "diff", "--name-only", f"{EXPECTED_PHASE2_COMMIT}..HEAD")
    except Phase3VerificationError as exc:
        return [str(exc)]
    changed = [x.strip().replace("\\", "/") for x in output.splitlines()]
    bad = [x for x in changed if x and not _path_allowed(x)]
    return [] if not bad else [
        "Phase III changed paths outside the evaluation/presentation allowlist: "
        + ", ".join(sorted(bad))
    ]

def verify_required_files(root: Path) -> list[str]:
    missing = [x for x in REQUIRED_PHASE3_FILES if not (root / x).is_file()]
    return [] if not missing else ["Required Phase III files are missing: " + ", ".join(missing)]

def _run_python_check(root: Path, command: list[str], label: str) -> list[str]:
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True)
    return [] if completed.returncode == 0 else [
        f"{label} failed:\n" + completed.stdout + completed.stderr
    ]

def verify_frozen_releases(root: Path) -> list[str]:
    errors: list[str] = []
    errors += _run_python_check(
        root, ["python", "scripts/verify_phase2_release.py", "--require-tag"],
        "Frozen Phase II release verifier",
    )
    errors += _run_python_check(
        root, ["python", "scripts/verify_model1d_v038_release.py", "--require-tags"],
        "Frozen Model 1D v0.3.8 verifier",
    )
    return errors

def verify_no_tracked_runtime_artifacts(root: Path) -> list[str]:
    try:
        tracked = _git(root, "ls-files").splitlines()
    except Phase3VerificationError as exc:
        return [str(exc)]
    bad = []
    for raw in tracked:
        path = raw.replace("\\", "/")
        lower = path.lower()
        if lower.startswith("data/backups/") or lower.endswith(".duckdb") or lower.endswith(".wal"):
            bad.append(path)
        elif lower.startswith("reports/decision_intelligence_snapshots/"):
            bad.append(path)
    return [] if not bad else ["Tracked runtime/evaluation artifacts are forbidden: " + ", ".join(sorted(bad))]

def verify_branch(root: Path) -> list[str]:
    try:
        branch = _git(root, "branch", "--show-current")
    except Phase3VerificationError as exc:
        return [str(exc)]
    return [] if branch == EXPECTED_BRANCH else [
        f"Phase III hardening must run on {EXPECTED_BRANCH}; found {branch!r}."
    ]

def main() -> int:
    parser = argparse.ArgumentParser(description="Verify MacroPulse Phase III hardening boundary.")
    parser.add_argument("--skip-frozen-release-verifiers", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    errors += verify_branch(root)
    errors += verify_boundary(root)
    errors += verify_phase2_ancestry(root)
    errors += verify_phase3_change_isolation(root)
    errors += verify_required_files(root)
    errors += verify_no_tracked_runtime_artifacts(root)
    if not args.skip_frozen_release_verifiers:
        errors += verify_frozen_releases(root)
    if errors:
        print("Phase III evaluation hardening verification: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Phase III evaluation hardening verification: PASS")
    print(f"Branch: {EXPECTED_BRANCH}")
    print(f"Phase II base: {EXPECTED_PHASE2_TAG} -> {EXPECTED_PHASE2_COMMIT[:7]}")
    print("Phase III change isolation: PASS")
    print("Evaluation/no-look-ahead/vintage boundaries: PASS")
    print("Tracked runtime artifacts: none")
    if args.skip_frozen_release_verifiers:
        print("Frozen release verifiers: skipped by request")
    else:
        print("Phase II release boundary: PASS")
        print("Model 1D v0.3.8 boundary: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

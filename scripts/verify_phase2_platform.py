from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Iterable


EXPECTED_MODEL_SUITE = {
    "1A": ("production", "1.0.0"),
    "1B": ("production", "1.0.0"),
    "1C": ("production", "1.0.0"),
    "1D": ("development", "0.3.8"),
}


class VerificationError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"git {' '.join(args)} failed:\n"
            + completed.stdout
            + completed.stderr
        )
    return completed.stdout.strip()


def _tracked_files(root: Path) -> list[str]:
    return [
        line.replace("\\", "/")
        for line in _git(root, "ls-files").splitlines()
        if line.strip()
    ]


def _tracked_files_at_ref(root: Path, ref: str) -> list[str]:
    return [
        line.replace("\\", "/")
        for line in _git(
            root,
            "ls-tree",
            "-r",
            "--name-only",
            ref,
        ).splitlines()
        if line.strip()
    ]


def _matches_prefix_or_glob(path: str, pattern: str) -> bool:
    normalized = pattern.replace("\\", "/")
    if normalized.endswith("/"):
        return path.startswith(normalized)
    return fnmatch.fnmatch(path, normalized)


def validate_contract_files(
    root: Path,
    contract: dict,
    *,
    tracked_files: Iterable[str] | None = None,
    baseline_tracked_files: Iterable[str] | None = None,
) -> list[str]:
    errors: list[str] = []

    boundary_path = root / "PHASE2_BOUNDARY.json"
    if not boundary_path.is_file():
        return ["PHASE2_BOUNDARY.json is missing."]

    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    if boundary.get("phase") != "II":
        errors.append("Phase II boundary identity changed.")
    if boundary.get("branch") != contract["branch"]:
        errors.append("Phase II branch identity changed.")
    if boundary.get("base_commit") != contract["protected_base_commit"]:
        errors.append("Protected Phase II base commit changed.")
    if boundary.get("phase2_may_change_model_specifications") is not False:
        errors.append("Model-specification boundary is not fail-closed.")
    if boundary.get("phase2_may_tune_model1d_on_prospective_outcomes") is not False:
        errors.append("Model 1D prospective tuning boundary changed.")
    if boundary.get("phase2_may_move_model1d_release_tags") is not False:
        errors.append("Model 1D release-tag boundary changed.")

    suite = boundary.get("model_suite", {})
    for component, (lifecycle, version) in EXPECTED_MODEL_SUITE.items():
        item = suite.get(component, {})
        if item.get("status") != lifecycle or item.get("version") != version:
            errors.append(
                f"{component} identity changed: "
                f"expected {lifecycle} v{version}."
            )
    model1d = suite.get("1D", {})
    if model1d.get("mode") != "prospective_shadow":
        errors.append("Model 1D is no longer prospective_shadow.")
    if model1d.get("promotion_authority") != "none":
        errors.append("Model 1D promotion authority changed.")

    for relative in contract["required_platform_files"]:
        if not (root / relative).is_file():
            errors.append(f"Required platform file missing: {relative}")

    tracked = (
        list(tracked_files)
        if tracked_files is not None
        else _tracked_files(root)
    )
    baseline = set(
        baseline_tracked_files
        if baseline_tracked_files is not None
        else _tracked_files_at_ref(
            root,
            contract["protected_base_commit"],
        )
    )

    for path in tracked:
        if path in baseline:
            continue
        for pattern in contract["forbidden_new_tracked_artifacts"]:
            if _matches_prefix_or_glob(path, pattern):
                errors.append(
                    "New forbidden operational artifact is tracked after "
                    f"{contract['protected_base_commit']}: {path}"
                )
                break

    return errors


def validate_static_safety(root: Path) -> list[str]:
    errors: list[str] = []

    orchestration = (
        root / "scripts" / "run_platform_operations.py"
    ).read_text(encoding="utf-8")
    if "--execute" not in orchestration:
        errors.append("Orchestration lost explicit --execute gating.")
    if "--run-model1d" not in orchestration:
        errors.append("Orchestration lost explicit Model 1D opt-in.")
    if "if args.execute" not in orchestration:
        errors.append("Orchestration is not dry-run by default.")

    dashboard = (
        root / "ui" / "platform_dashboard.py"
    ).read_text(encoding="utf-8")
    forbidden_dashboard_markers = (
        ".query_df(",
        "repository.initialise(",
        "run_baseline_nowcast",
        "run_inflation_nowcast",
        "run_labour_nowcast",
        "run_macro_state_shadow_operations",
        "download_fred_data",
        "download_inflation_data",
        "download_labour_data",
    )
    for marker in forbidden_dashboard_markers:
        if marker in dashboard:
            errors.append(
                f"Dashboard contains forbidden execution/database marker: {marker}"
            )

    snapshot = (
        root / "src" / "macropulse" / "platform" / "snapshot.py"
    ).read_text(encoding="utf-8")
    forbidden_snapshot_markers = (
        "run_baseline_nowcast",
        "run_inflation_nowcast",
        "run_labour_nowcast",
        "run_macro_state_shadow_operations",
        "download_fred_data",
        "download_inflation_data",
        "download_labour_data",
    )
    for marker in forbidden_snapshot_markers:
        if marker in snapshot:
            errors.append(
                f"Snapshot contains forbidden execution marker: {marker}"
            )

    return errors


def validate_git_ancestry(root: Path, protected_base_commit: str) -> list[str]:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", protected_base_commit, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return []
    return [
        f"HEAD no longer descends from protected Phase II base "
        f"{protected_base_commit}."
    ]


def verify_model1d_release(root: Path, *, require_tags: bool) -> list[str]:
    command = ["python", "scripts/verify_model1d_v038_release.py"]
    if require_tags:
        command.append("--require-tags")
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return []
    return [
        "Frozen Model 1D release verifier failed:\n"
        + completed.stdout
        + completed.stderr
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the MacroPulse Phase II platform release boundary."
    )
    parser.add_argument(
        "--require-model1d-tags",
        action="store_true",
        help="Require the published Model 1D v0.3.8 tags.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    contract_path = root / "PHASE2_PLATFORM_CONTRACT.json"
    if not contract_path.is_file():
        print("Phase II platform verification: FAIL")
        print("PHASE2_PLATFORM_CONTRACT.json is missing.")
        return 1

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    errors.extend(validate_contract_files(root, contract))
    errors.extend(validate_static_safety(root))
    errors.extend(
        validate_git_ancestry(root, contract["protected_base_commit"])
    )
    errors.extend(
        verify_model1d_release(
            root,
            require_tags=args.require_model1d_tags,
        )
    )

    if errors:
        print("Phase II platform verification: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    tracked_count = len(_tracked_files(root))
    print("Phase II platform verification: PASS")
    print(f"Platform version: {contract['platform_version']}")
    print(f"Lifecycle: {contract['lifecycle']}")
    print(f"Tracked files inspected: {tracked_count}")
    print("Phase II model-governance boundary: PASS")
    print("New operational artifact tracking guard: PASS")
    print("Dashboard read-only structural guard: PASS")
    print("Snapshot no-execution structural guard: PASS")
    print("Protected base ancestry: PASS")
    print("Frozen Model 1D release verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

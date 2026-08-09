from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


EXPECTED_RELEASE_ID = "MACROPULSE_PHASE2_PLATFORM_V1_0_0"
EXPECTED_VERSION = "1.0.0"
EXPECTED_TAG = "phase2-platform-v1.0.0"
EXPECTED_SOURCE_COMMIT = "bd98dde68b32b9b71e54c8cc797205fa5627641b"
EXPECTED_CI_RUN_ID = 31307316856
EXPECTED_CI_RUN_NUMBER = 2


class ReleaseVerificationError(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ReleaseVerificationError(
            f"git {' '.join(args)} failed:\n"
            + completed.stdout
            + completed.stderr
        )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict[str, str]:
    manifest = root / "MANIFEST_PHASE2_v1.0.0.txt"
    if not manifest.is_file():
        raise ReleaseVerificationError("Phase II release manifest is missing.")

    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    if not entries:
        raise ReleaseVerificationError("Phase II release manifest is empty.")
    return entries


def verify_manifest(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        entries = load_manifest(root)
    except ReleaseVerificationError as exc:
        return [str(exc)]

    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"Manifest file missing: {relative}")
            continue
        actual = _sha256(path)
        if actual != expected:
            errors.append(
                f"Manifest hash mismatch: {relative}; "
                f"expected {expected}, found {actual}"
            )
    return errors


def verify_metadata(root: Path) -> list[str]:
    errors: list[str] = []
    release_path = root / "PHASE2_RELEASE.json"
    contract_path = root / "PHASE2_PLATFORM_CONTRACT.json"

    if not release_path.is_file():
        return ["PHASE2_RELEASE.json is missing."]
    if not contract_path.is_file():
        return ["PHASE2_PLATFORM_CONTRACT.json is missing."]

    release = json.loads(release_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    if release.get("release_id") != EXPECTED_RELEASE_ID:
        errors.append("Unexpected Phase II release identity.")
    if release.get("platform_version") != EXPECTED_VERSION:
        errors.append("Unexpected Phase II release version.")
    if release.get("lifecycle") != "released":
        errors.append("Phase II release lifecycle is not released.")
    if release.get("release_tag") != EXPECTED_TAG:
        errors.append("Unexpected Phase II release tag.")
    if release.get("closure_source_commit") != EXPECTED_SOURCE_COMMIT:
        errors.append("Unexpected release closure source commit.")

    ci = release.get("ci_release_gate", {})
    if ci.get("status") != "success":
        errors.append("Recorded CI release gate is not successful.")
    if ci.get("run_id") != EXPECTED_CI_RUN_ID:
        errors.append("Unexpected CI release-gate run ID.")
    if ci.get("run_number") != EXPECTED_CI_RUN_NUMBER:
        errors.append("Unexpected CI release-gate run number.")
    if ci.get("commit") != EXPECTED_SOURCE_COMMIT:
        errors.append("CI release-gate commit does not match closure source.")

    if contract.get("platform_version") != EXPECTED_VERSION:
        errors.append("Platform contract version changed.")
    if contract.get("lifecycle") != "released":
        errors.append("Platform contract lifecycle is not released.")
    if contract.get("release_tag") != EXPECTED_TAG:
        errors.append("Platform contract release tag changed.")

    suite = release.get("model_suite", {})
    expected = {
        "1A": ("production", "1.0.0"),
        "1B": ("production", "1.0.0"),
        "1C": ("production", "1.0.0"),
        "1D": ("development", "0.3.8"),
    }
    for component, (lifecycle, version) in expected.items():
        item = suite.get(component, {})
        if item.get("lifecycle") != lifecycle or item.get("version") != version:
            errors.append(
                f"{component} release model identity changed."
            )

    model1d = suite.get("1D", {})
    if model1d.get("mode") != "prospective_shadow":
        errors.append("Model 1D release mode changed.")
    if model1d.get("promotion_authority") != "none":
        errors.append("Model 1D promotion authority changed.")

    return errors


def verify_source_ancestry(root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", EXPECTED_SOURCE_COMMIT, "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return []
    return [
        "Release closure HEAD does not descend from the successful "
        f"CI source commit {EXPECTED_SOURCE_COMMIT}."
    ]


def verify_platform_boundary(root: Path) -> list[str]:
    completed = subprocess.run(
        [
            "python",
            "scripts/verify_phase2_platform.py",
            "--require-model1d-tags",
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return []
    return [
        "Phase II platform boundary verifier failed:\n"
        + completed.stdout
        + completed.stderr
    ]


def verify_release_tag(root: Path) -> list[str]:
    try:
        tag_commit = _git(root, "rev-parse", f"{EXPECTED_TAG}^{{commit}}")
        release_commit = _git(
            root,
            "log",
            "-1",
            "--format=%H",
            "--",
            "PHASE2_RELEASE.json",
        )
    except ReleaseVerificationError as exc:
        return [str(exc)]

    if not release_commit:
        return ["Unable to resolve the Phase II release-closure commit."]
    if tag_commit != release_commit:
        return [
            f"Release tag {EXPECTED_TAG} points to {tag_commit}, "
            f"but PHASE2_RELEASE.json was introduced/last changed at "
            f"{release_commit}."
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify MacroPulse Phase II platform v1.0.0 release."
    )
    parser.add_argument(
        "--require-tag",
        action="store_true",
        help=(
            "Require phase2-platform-v1.0.0 and verify it points to the "
            "release-closure commit."
        ),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    errors.extend(verify_metadata(root))
    errors.extend(verify_manifest(root))
    errors.extend(verify_source_ancestry(root))
    errors.extend(verify_platform_boundary(root))
    if args.require_tag:
        errors.extend(verify_release_tag(root))

    if errors:
        print("Phase II platform v1.0.0 release verification: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    entries = load_manifest(root)
    print("Phase II platform v1.0.0 release verification: PASS")
    print(f"Manifest files verified: {len(entries)}")
    print(f"Closure source commit: {EXPECTED_SOURCE_COMMIT}")
    print(f"CI release gate: Phase II Platform Guard #{EXPECTED_CI_RUN_NUMBER} PASS")
    print("Phase II platform boundary: PASS")
    print("Model 1D research boundary: PASS")
    if args.require_tag:
        print(f"Release tag: {EXPECTED_TAG} -> release closure commit")
    else:
        print(f"Release tag requirement: not requested ({EXPECTED_TAG})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

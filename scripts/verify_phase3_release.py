from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = PROJECT_ROOT / "PHASE3_RELEASE.json"
MANIFEST_FILE = PROJECT_ROOT / "MANIFEST_PHASE3_v1.0.0.txt"

TAG = "phase3-evaluation-v1.0.0"
EXPECTED_BRANCH = "phase3-evaluation-development"
PHASE2_TAG = "phase2-platform-v1.0.0"
PHASE2_COMMIT = "43395d889a76453706259a5095bd718337b55851"
SOURCE_GATE_COMMIT = "ac8af6425cdb79e1516614328b52ab761be1ffe4"
SOURCE_GATE_RUN_ID = 31425130485
SOURCE_GATE_RUN_NUMBER = 1
SOURCE_GATE_JOB_ID = 93574903444
SNAPSHOT_HASH = "8a8dca1095109d9ea3d2540ee264cae407598847117bd5dd1a4f6ef9dfd5ce11"

CLOSURE_WORKING_PATHS = {
    ".github/workflows/phase3-evaluation-guard.yml",
    "PHASE3_BOUNDARY.json",
    "PHASE3_RELEASE.json",
    "README_PHASE3_v1.0.0.md",
    "VALIDATION_PHASE3_v1.0.0.txt",
    "scripts/verify_phase3_release.py",
    "tests/test_phase3_release_metadata.py",
    "tests/test_phase3_release_manifest_integrity.py",
}


class ReleaseVerificationError(RuntimeError):
    pass


def _git(*args: str, binary: bool = False):
    completed = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=not binary
    )
    if completed.returncode != 0:
        stdout = completed.stdout if not binary else completed.stdout.decode(errors="replace")
        stderr = completed.stderr if not binary else completed.stderr.decode(errors="replace")
        raise ReleaseVerificationError(
            f"git {' '.join(args)} failed:\n{stdout}{stderr}"
        )
    return completed.stdout


def _git_text(*args: str) -> str:
    return str(_git(*args)).strip()


def _head() -> str:
    return _git_text("rev-parse", "HEAD")


def _tracked_blob(path: str, ref: str = "HEAD") -> bytes:
    return bytes(_git("show", f"{ref}:{path}", binary=True))


def load_release() -> dict:
    if not RELEASE_FILE.is_file():
        raise ReleaseVerificationError("PHASE3_RELEASE.json is missing.")
    return json.loads(RELEASE_FILE.read_text(encoding="utf-8"))


def load_manifest() -> dict[str, str]:
    if not MANIFEST_FILE.is_file():
        raise ReleaseVerificationError("MANIFEST_PHASE3_v1.0.0.txt is missing.")
    entries: dict[str, str] = {}
    for raw in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, path = line.split("  ", 1)
        if path in entries:
            raise ReleaseVerificationError(f"Duplicate manifest path: {path}")
        entries[path] = digest
    return entries


def verify_release_record(release: dict, manifest: dict[str, str]) -> list[str]:
    errors: list[str] = []
    expected = {
        "internal_phase": "III",
        "roadmap_phase": "I",
        "platform_version": "1.0.0",
        "status": "released",
        "release_tag": TAG,
        "release_branch": EXPECTED_BRANCH,
    }
    for key, value in expected.items():
        if release.get(key) != value:
            errors.append(f"Release record mismatch for {key}: {release.get(key)!r}")

    if release.get("base_release", {}).get("tag") != PHASE2_TAG:
        errors.append("Phase II base release tag changed.")
    if release.get("base_release", {}).get("commit") != PHASE2_COMMIT:
        errors.append("Phase II base release commit changed.")

    source = release.get("closure_source_commit", {})
    if source.get("sha") != SOURCE_GATE_COMMIT:
        errors.append("Phase III closure source commit changed.")

    ci = release.get("ci_evidence", {}).get("phase3_evaluation_guard", {})
    checks = {
        "workflow": "Phase III Evaluation Guard",
        "run_number": SOURCE_GATE_RUN_NUMBER,
        "run_id": SOURCE_GATE_RUN_ID,
        "job_id": SOURCE_GATE_JOB_ID,
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE_GATE_COMMIT,
        "branch": EXPECTED_BRANCH,
    }
    for key, value in checks.items():
        if ci.get(key) != value:
            errors.append(f"Source CI evidence mismatch for {key}: {ci.get(key)!r}")

    deterministic = release.get("deterministic_snapshot_evidence", {})
    if deterministic.get("snapshot_hash") != SNAPSHOT_HASH:
        errors.append("Phase 3E deterministic snapshot hash changed.")

    if release.get("manifest_file") != MANIFEST_FILE.name:
        errors.append("Release record manifest filename changed.")
    if release.get("manifest_file_count") != len(manifest):
        errors.append("Release record manifest count does not match manifest.")

    authority = release.get("execution_authority", {})
    for key in (
        "automatic_model_action",
        "governed_forecast_mutation",
        "model_execution",
        "model1d_promotion_authority",
    ):
        if authority.get(key) != "none":
            errors.append(f"Release execution authority changed: {key}")

    expected_note = (
        "This internal Phase III evaluation layer supports the overall "
        "MacroPulse roadmap Phase I (Model 1); it is not roadmap Phase III "
        "(Models 5-7)."
    )
    if release.get("roadmap_note") != expected_note:
        errors.append("MacroPulse roadmap context changed.")
    return errors


def verify_boundary() -> list[str]:
    payload = json.loads((PROJECT_ROOT / "PHASE3_BOUNDARY.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    if payload.get("status") != "released":
        errors.append("PHASE3_BOUNDARY.json status must be released.")
    if payload.get("base_release_tag") != PHASE2_TAG:
        errors.append("Phase III boundary Phase II tag changed.")
    if payload.get("base_release_commit") != PHASE2_COMMIT:
        errors.append("Phase III boundary Phase II commit changed.")
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
            errors.append(f"Fail-closed boundary changed: {key}")
    return errors


def _bytes_for_manifest_path(path: str, head: str) -> bytes:
    if head == SOURCE_GATE_COMMIT and path in CLOSURE_WORKING_PATHS:
        candidate = PROJECT_ROOT / path
        if not candidate.is_file():
            raise ReleaseVerificationError(f"Closure working file is missing: {path}")
        return candidate.read_bytes()
    return _tracked_blob(path, "HEAD")


def verify_manifest(manifest: dict[str, str]) -> list[str]:
    errors: list[str] = []
    head = _head()
    if MANIFEST_FILE.name in manifest:
        errors.append("Manifest must not hash itself.")
    for path, expected_digest in manifest.items():
        try:
            content = _bytes_for_manifest_path(path, head)
        except ReleaseVerificationError as exc:
            errors.append(str(exc))
            continue
        actual = hashlib.sha256(content).hexdigest()
        if actual != expected_digest:
            errors.append(
                f"Manifest checksum mismatch: {path} "
                f"(expected {expected_digest}, got {actual})"
            )
    return errors


def verify_source_identity(manifest: dict[str, str]) -> list[str]:
    head = _head()
    if head == SOURCE_GATE_COMMIT:
        return []

    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE_GATE_COMMIT, head],
        cwd=PROJECT_ROOT,
    )
    if ancestor.returncode != 0:
        return ["Release HEAD does not descend from the Phase 3F.1 source-gate commit."]

    try:
        count = int(_git_text("rev-list", "--count", f"{SOURCE_GATE_COMMIT}..{head}"))
    except (ReleaseVerificationError, ValueError) as exc:
        return [str(exc)]
    if count != 1:
        return [
            "Phase III release closure must be exactly one commit after the "
            f"source-gate commit; found {count} commit(s)."
        ]

    changed = {
        line.strip().replace("\\", "/")
        for line in _git_text("diff", "--name-only", f"{PHASE2_COMMIT}..{head}").splitlines()
        if line.strip()
    }
    expected_changed = set(manifest) | {MANIFEST_FILE.name}
    if changed != expected_changed:
        missing = sorted(expected_changed - changed)
        extra = sorted(changed - expected_changed)
        details: list[str] = []
        if missing:
            details.append("missing from committed Phase III delta: " + ", ".join(missing))
        if extra:
            details.append("unexpected committed Phase III delta: " + ", ".join(extra))
        return ["Phase III release source identity mismatch: " + "; ".join(details)]
    return []


def verify_frozen_releases() -> list[str]:
    checks = (
        (["python", "scripts/verify_phase2_release.py", "--require-tag"], "Phase II release verifier"),
        (["python", "scripts/verify_model1d_v038_release.py", "--require-tags"], "Model 1D v0.3.8 release verifier"),
    )
    errors: list[str] = []
    for command, label in checks:
        completed = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
        if completed.returncode != 0:
            errors.append(f"{label} failed:\n{completed.stdout}{completed.stderr}")
    return errors


def verify_no_tracked_runtime_artifacts() -> list[str]:
    tracked = _git_text("ls-files").splitlines()
    bad: list[str] = []
    for raw in tracked:
        path = raw.replace("\\", "/")
        lower = path.lower()
        if lower.startswith("data/backups/"):
            bad.append(path)
        elif lower.endswith(".duckdb") or lower.endswith(".wal"):
            bad.append(path)
        elif lower.startswith("reports/decision_intelligence_snapshots/"):
            bad.append(path)
    return [] if not bad else ["Tracked runtime artifacts are forbidden: " + ", ".join(sorted(bad))]


def verify_tag(require_tag: bool) -> list[str]:
    matching = _git_text("tag", "--list", TAG)
    if not matching:
        return [f"Required release tag is missing: {TAG}"] if require_tag else []
    target = _git_text("rev-list", "-n", "1", TAG)
    head = _head()
    if target != head:
        return [f"Release tag {TAG} does not point at HEAD."]
    if head == SOURCE_GATE_COMMIT:
        return ["Release tag may not point at the Phase 3F.1 source-gate commit."]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify MacroPulse internal Phase III evaluation release v1.0.0."
    )
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument("--skip-frozen-release-verifiers", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        release = load_release()
        manifest = load_manifest()
        errors += verify_release_record(release, manifest)
        errors += verify_boundary()
        errors += verify_manifest(manifest)
        errors += verify_source_identity(manifest)
        errors += verify_no_tracked_runtime_artifacts()
        errors += verify_tag(args.require_tag)
        if not args.skip_frozen_release_verifiers:
            errors += verify_frozen_releases()
    except (ReleaseVerificationError, json.JSONDecodeError, OSError, ValueError) as exc:
        errors.append(str(exc))

    if errors:
        print("Phase III evaluation v1.0.0 release verification: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Phase III evaluation v1.0.0 release verification: PASS")
    print(f"Release tag policy: {TAG} (immutable; required only with --require-tag)")
    print(f"Closure source commit: {SOURCE_GATE_COMMIT[:7]}")
    print(
        "Source CI gate: Phase III Evaluation Guard "
        f"#{SOURCE_GATE_RUN_NUMBER} / run {SOURCE_GATE_RUN_ID} PASS"
    )
    print(f"Manifest files verified: {len(load_manifest())}")
    print("Phase II release boundary: PASS")
    print("Model 1D v0.3.8 boundary: PASS")
    print("Tracked runtime artifacts: none")
    print("Automatic model action: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

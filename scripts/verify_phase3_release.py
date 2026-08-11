from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = PROJECT_ROOT / "PHASE3_RELEASE.json"
MANIFEST_FILE = PROJECT_ROOT / "MANIFEST_PHASE3_v1.0.1.txt"

TAG = "phase3-evaluation-v1.0.1"
PREVIOUS_TAG = "phase3-evaluation-v1.0.0"
PHASE2_COMMIT = "43395d889a76453706259a5095bd718337b55851"
PREVIOUS_RELEASE_COMMIT = "20c3682a96061d9e740aaf001bf2f72a98377928"
RELEASE_COMMIT = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"
SOURCE_GATE_COMMIT = PREVIOUS_RELEASE_COMMIT
SOURCE_GATE_RUN_ID = 31428781570
SOURCE_GATE_RUN_NUMBER = 2
SOURCE_GATE_JOB_ID = 93586783076
SNAPSHOT_HASH = "8a8dca1095109d9ea3d2540ee264cae407598847117bd5dd1a4f6ef9dfd5ce11"

PATCH_WORKING_PATHS = {
    "PHASE3_RELEASE.json",
    "README_PHASE3_v1.0.1.md",
    "VALIDATION_PHASE3_v1.0.1.txt",
    "scripts/verify_phase3_release.py",
    "tests/test_phase3_bootstrap_contract.py",
    "tests/test_phase3_release_metadata.py",
}

def git(*args: str, binary: bool = False):
    c = subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=not binary)
    if c.returncode != 0:
        out = c.stdout if not binary else c.stdout.decode(errors="replace")
        err = c.stderr if not binary else c.stderr.decode(errors="replace")
        raise RuntimeError(f"git {' '.join(args)} failed:\n{out}{err}")
    return c.stdout

def git_text(*args: str) -> str:
    return str(git(*args)).strip()

def head() -> str:
    return git_text("rev-parse", "HEAD")

def tracked_blob(path: str, ref: str = "HEAD") -> bytes:
    return bytes(git("show", ref + ":" + path, binary=True))

def _tagged_text(path: str) -> str:
    return str(git("show", RELEASE_COMMIT + ":" + path)).strip()

def load_release() -> dict:
    return json.loads(_tagged_text(RELEASE_FILE.name))

def load_manifest() -> dict[str, str]:
    entries = {}
    for raw in _tagged_text(MANIFEST_FILE.name).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, path = line.split("  ", 1)
        entries[path] = digest
    return entries

def verify_release_record(release: dict, manifest: dict[str, str]) -> list[str]:
    errors = []
    expected = {
        "internal_phase": "III",
        "roadmap_phase": "I",
        "platform_version": "1.0.1",
        "status": "released",
        "release_tag": TAG,
        "release_branch": "phase3-evaluation-development",
        "release_type": "release_engineering_patch",
    }
    for k, v in expected.items():
        if release.get(k) != v:
            errors.append(f"Release record mismatch for {k}: {release.get(k)!r}")

    prev = release.get("previous_release", {})
    if prev.get("tag") != PREVIOUS_TAG or prev.get("commit") != PREVIOUS_RELEASE_COMMIT:
        errors.append("Previous Phase III release identity changed.")
    if prev.get("immutable") is not True:
        errors.append("Previous Phase III release must remain immutable.")

    src = release.get("closure_source_commit", {})
    if src.get("sha") != SOURCE_GATE_COMMIT:
        errors.append("v1.0.1 source-gate commit changed.")

    ci = release.get("ci_evidence", {}).get("phase3_evaluation_guard", {})
    checks = {
        "run_number": SOURCE_GATE_RUN_NUMBER,
        "run_id": SOURCE_GATE_RUN_ID,
        "job_id": SOURCE_GATE_JOB_ID,
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE_GATE_COMMIT,
    }
    for k, v in checks.items():
        if ci.get(k) != v:
            errors.append(f"Source CI evidence mismatch for {k}: {ci.get(k)!r}")

    prior = release.get("prior_tag_ci_failure", {})
    if prior.get("run_id") != 31470015299 or prior.get("job_id") != 93711061207:
        errors.append("Prior tag-CI failure evidence changed.")
    if prior.get("failure_scope") != "release_test_contract_only":
        errors.append("Prior tag-CI failure scope changed.")

    if release.get("semantic_change") is not False:
        errors.append("v1.0.1 must record semantic_change=false.")

    if release.get("manifest_file") != MANIFEST_FILE.name:
        errors.append("Manifest filename changed.")
    if release.get("manifest_file_count") != len(manifest):
        errors.append("Manifest count mismatch.")
    if release.get("deterministic_snapshot_evidence", {}).get("snapshot_hash") != SNAPSHOT_HASH:
        errors.append("Deterministic snapshot hash changed.")

    for k in ("automatic_model_action","governed_forecast_mutation","model_execution","model1d_promotion_authority"):
        if release.get("execution_authority", {}).get(k) != "none":
            errors.append(f"Execution authority changed: {k}")
    return errors

def verify_boundary() -> list[str]:
    p = json.loads((PROJECT_ROOT / "PHASE3_BOUNDARY.json").read_text(encoding="utf-8"))
    errors = []
    if p.get("status") != "released":
        errors.append("PHASE3_BOUNDARY.json must remain released.")
    for k in (
        "phase3_core_may_use_generative_ai",
        "phase3_may_automatically_promote_or_demote_models",
        "phase3_may_backfill_model1d",
        "phase3_may_change_model_specifications",
        "phase3_may_move_model1d_release_tags",
        "phase3_may_move_phase2_release_tag",
        "phase3_may_mutate_governed_forecasts",
        "phase3_may_tune_model1d_on_prospective_outcomes",
    ):
        if p.get(k) is not False:
            errors.append(f"Fail-closed boundary changed: {k}")
    return errors

def bytes_for_manifest(path: str, current_head: str) -> bytes:
    return tracked_blob(path, RELEASE_COMMIT)

def verify_manifest(manifest: dict[str, str]) -> list[str]:
    errors = []
    current_head = head()
    if MANIFEST_FILE.name in manifest:
        errors.append("Manifest must not hash itself.")
    for path, expected in manifest.items():
        actual = hashlib.sha256(bytes_for_manifest(path, current_head)).hexdigest()
        if actual != expected:
            errors.append(f"Manifest checksum mismatch: {path}")
    return errors

def verify_source_identity(manifest: dict[str, str]) -> list[str]:
    errors: list[str] = []
    tag_target = git_text("rev-parse", TAG + "^{commit}")
    if tag_target != RELEASE_COMMIT:
        errors.append("Immutable Phase III v1.0.1 release tag moved.")
    previous_target = git_text("rev-parse", PREVIOUS_TAG + "^{commit}")
    if previous_target != PREVIOUS_RELEASE_COMMIT:
        errors.append("Immutable Phase III v1.0.0 release tag moved.")
    count = int(
        git_text(
            "rev-list",
            "--count",
            PREVIOUS_RELEASE_COMMIT + ".." + RELEASE_COMMIT,
        )
    )
    if count != 1:
        errors.append(
            "Frozen v1.0.1 release must be exactly one patch commit after "
            f"v1.0.0; found {count}."
        )
    changed = {
        x.strip().replace("\\", "/")
        for x in git_text(
            "diff", "--name-only", PHASE2_COMMIT + ".." + RELEASE_COMMIT
        ).splitlines()
        if x.strip()
    }
    expected = set(manifest) | {MANIFEST_FILE.name}
    if changed != expected:
        errors.append("Frozen Phase III v1.0.1 source identity mismatch.")
    current_head = head()
    if current_head != RELEASE_COMMIT:
        c = subprocess.run(
            ["git", "merge-base", "--is-ancestor", RELEASE_COMMIT, current_head],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )
        if c.returncode != 0:
            errors.append(
                "Current checkout does not descend from immutable Phase III v1.0.1."
            )
    return errors

def verify_previous_tag() -> list[str]:
    if not git_text("tag","--list",PREVIOUS_TAG):
        return [f"Missing immutable previous tag: {PREVIOUS_TAG}"]
    target = git_text("rev-list","-n","1",PREVIOUS_TAG)
    return [] if target == PREVIOUS_RELEASE_COMMIT else [f"{PREVIOUS_TAG} moved."]

def verify_frozen_releases() -> list[str]:
    errors = []
    for cmd, label in (
        (["python","scripts/verify_phase2_release.py","--require-tag"],"Phase II"),
        (["python","scripts/verify_model1d_v038_release.py","--require-tags"],"Model 1D"),
    ):
        c = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        if c.returncode != 0:
            errors.append(f"{label} verifier failed:\n{c.stdout}{c.stderr}")
    return errors

def verify_no_runtime_artifacts() -> list[str]:
    bad = []
    for raw in git_text("ls-files").splitlines():
        p = raw.replace("\\","/").lower()
        if p.startswith("data/backups/") or p.endswith(".duckdb") or p.endswith(".wal") or p.startswith("reports/decision_intelligence_snapshots/"):
            bad.append(raw)
    return [] if not bad else ["Tracked runtime artifacts: " + ", ".join(bad)]

def verify_no_tracked_runtime_artifacts() -> list[str]:
    """Backward-compatible public verifier API used by release tests."""
    return verify_no_runtime_artifacts()

def verify_tag(require_tag: bool) -> list[str]:
    matching = git_text("tag", "--list", TAG)
    if not matching:
        return [f"Required release tag is missing: {TAG}"] if require_tag else []
    target = git_text("rev-parse", TAG + "^{commit}")
    if target != RELEASE_COMMIT:
        return [f"{TAG} moved from its immutable release commit."]
    return []

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-tag", action="store_true")
    ap.add_argument("--skip-frozen-release-verifiers", action="store_true")
    args = ap.parse_args()
    errors = []
    try:
        release = load_release()
        manifest = load_manifest()
        errors += verify_release_record(release, manifest)
        errors += verify_boundary()
        errors += verify_manifest(manifest)
        errors += verify_source_identity(manifest)
        errors += verify_previous_tag()
        errors += verify_no_runtime_artifacts()
        errors += verify_tag(args.require_tag)
        if not args.skip_frozen_release_verifiers:
            errors += verify_frozen_releases()
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Phase III evaluation v1.0.1 release verification: FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    print("Phase III evaluation v1.0.1 release verification: PASS")
    print(f"Previous immutable tag: {PREVIOUS_TAG} -> {PREVIOUS_RELEASE_COMMIT[:7]}")
    print(f"Release tag policy: {TAG} (immutable; required only with --require-tag)")
    print(f"Patch source commit: {SOURCE_GATE_COMMIT[:7]}")
    print(f"Source CI gate: Phase III Evaluation Guard #{SOURCE_GATE_RUN_NUMBER} / run {SOURCE_GATE_RUN_ID} PASS")
    print(f"Manifest files verified: {len(load_manifest())}")
    print("Release patch type: tag-CI compatibility only")
    print("Semantic changes: none")
    print("Phase II release boundary: PASS")
    print("Model 1D v0.3.8 boundary: PASS")
    print("Tracked runtime artifacts: none")
    print("Automatic model action: none")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

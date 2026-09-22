from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = ROOT / "MODEL2_RELEASE.json"
MANIFEST_FILE = ROOT / "MANIFEST_MODEL2_v1.0.1.txt"

TAG = "model2-bvar-v1.0.1"
PREVIOUS_TAG = "model2-bvar-v1.0.0"
PREVIOUS_RELEASE_COMMIT = "22664c1d3a102ce88b62966dfb6c1f8a3405023f"
BASE_PHASE3 = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SOURCE_CI_RUN = 35769859027
SOURCE_CI_JOB = 106888547394
SOURCE_CI_NUMBER = 13
FAILED_TAG_RUN = 35775232829
FAILED_TAG_JOB = 106906660113
SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"

PATCH_PATHS = {
    "MODEL2_RELEASE.json",
    "MANIFEST_MODEL2_v1.0.1.txt",
    "README_MODEL2_v1.0.1.md",
    "VALIDATION_MODEL2_v1.0.1.txt",
    "scripts/verify_model2g_evaluation.py",
    "scripts/verify_model2h_production.py",
    "scripts/verify_model2_release.py",
    "tests/test_model2_release_metadata.py",
}

IGNORED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
)


def git(*args: str, binary: bool = False):
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=not binary,
    )
    if completed.returncode != 0:
        stdout = (
            completed.stdout.decode(errors="replace")
            if binary else completed.stdout
        )
        stderr = (
            completed.stderr.decode(errors="replace")
            if binary else completed.stderr
        )
        raise RuntimeError(
            "git " + " ".join(args) + " failed:\n" + stdout + stderr
        )
    return completed.stdout


def git_text(*args: str) -> str:
    return str(git(*args)).strip()


def names(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def ignorable(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES)


def tracked_blob(path: str, ref: str) -> bytes:
    return bytes(git("show", ref + ":" + path, binary=True))


def load_manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, path = line.split("  ", 1)
        entries[path] = digest
    return entries


def source_paths() -> set[str]:
    return names(
        git_text(
            "diff",
            "--diff-filter=ACMRT",
            "--name-only",
            BASE_PHASE3 + ".." + SOURCE_CLOSURE,
        )
    )


def observed_patch() -> set[str]:
    committed = names(
        git_text(
            "diff",
            "--name-only",
            PREVIOUS_RELEASE_COMMIT + "..HEAD",
        )
    )
    working = {
        path
        for path in names(git_text("diff", "--name-only"))
        if not ignorable(path)
    }
    staged = names(git_text("diff", "--cached", "--name-only"))
    untracked = {
        path
        for path in names(
            git_text("ls-files", "--others", "--exclude-standard")
        )
        if not ignorable(path)
    }
    return committed | working | staged | untracked


def verify_release_record(
    release: dict,
    manifest: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    expected = {
        "roadmap_phase": "II",
        "model": "2",
        "model_name": "Bayesian VAR",
        "version": "1.0.1",
        "release_tag": TAG,
        "release_branch": "model2-bvar-development",
        "release_type": "release_engineering_patch",
        "semantic_change": False,
    }
    for key, value in expected.items():
        if release.get(key) != value:
            errors.append("Release record mismatch for " + key)

    source = release.get("source_closure", {})
    if source.get("commit") != SOURCE_CLOSURE:
        errors.append("Model 2 source closure changed.")

    ci = source.get("ci", {})
    expected_ci = {
        "workflow": "Model 2 Bayesian VAR Guard",
        "run_number": SOURCE_CI_NUMBER,
        "run_id": SOURCE_CI_RUN,
        "job_id": SOURCE_CI_JOB,
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE_CLOSURE,
    }
    for key, value in expected_ci.items():
        if ci.get(key) != value:
            errors.append("Source CI evidence mismatch for " + key)

    previous = release.get("previous_release", {})
    if previous.get("tag") != PREVIOUS_TAG:
        errors.append("Previous immutable tag identity changed.")
    if previous.get("commit") != PREVIOUS_RELEASE_COMMIT:
        errors.append("Previous immutable tag commit changed.")
    if previous.get("immutable") is not True:
        errors.append("Previous v1.0.0 tag must remain immutable.")
    if previous.get("move_or_recreate") is not False:
        errors.append("Previous v1.0.0 tag movement policy changed.")

    failure = release.get("prior_tag_ci_failure", {})
    if failure.get("run_id") != FAILED_TAG_RUN:
        errors.append("Prior failed tag-CI run identity changed.")
    if failure.get("job_id") != FAILED_TAG_JOB:
        errors.append("Prior failed tag-CI job identity changed.")
    if failure.get("failure_scope") != "release_verifier_contract_only":
        errors.append("Prior tag-CI failure classification changed.")
    if failure.get("model_or_forecast_semantics_affected") is not False:
        errors.append("Prior tag-CI failure must remain non-semantic.")

    selected = release.get("selected_specification", {})
    if selected.get("candidate_id") != SELECTED_ID:
        errors.append("Released candidate ID changed.")
    if selected.get("lags") != 2:
        errors.append("Released lag order changed.")
    if abs(float(selected.get("shrinkage", -1.0)) - 0.1) > 1e-12:
        errors.append("Released shrinkage changed.")
    if selected.get("selection_evidence_payload_hash") != EVIDENCE_HASH:
        errors.append("Selection evidence identity changed.")

    patch_scope = release.get("patch_scope", {})
    for key in (
        "model_logic",
        "forecast_semantics",
        "selected_specification",
        "structural_identification",
        "scenario_semantics",
        "pseudo_real_time_evidence",
        "source_manifest",
    ):
        if patch_scope.get(key) != "unchanged":
            errors.append("Compatibility patch scope changed: " + key)
    if patch_scope.get("tag_checkout_contract") != "detached_head_compatible":
        errors.append("Detached-HEAD compatibility scope changed.")

    if release.get("manifest_file") != MANIFEST_FILE.name:
        errors.append("Manifest filename changed.")
    if release.get("manifest_file_count") != len(manifest):
        errors.append("Manifest file count changed.")
    if (
        release.get("manifest_sha256")
        != hashlib.sha256(MANIFEST_FILE.read_bytes()).hexdigest()
    ):
        errors.append("Manifest SHA-256 changed.")

    governance = release.get("governance", {})
    for key in (
        "candidate_specification_immutable",
        "prospective_retuning_prohibited",
        "automatic_switching_prohibited",
        "model1d_prospective_outcomes_excluded",
        "historical_model1_backfill_prohibited",
        "generative_ai_in_governed_core_prohibited",
    ):
        if governance.get(key) is not True:
            errors.append("Release governance changed: " + key)

    authority = release.get("execution_authority", {})
    if (
        authority.get("core_forecast_interface")
        != "authorized_when_tag_verified"
    ):
        errors.append("Core forecast authority boundary changed.")
    for key in (
        "automatic_model_switching",
        "automatic_candidate_reselection",
        "database_write_authority",
        "scenario_probability_authority",
        "unidentified_causal_claim_authority",
    ):
        if authority.get(key) != "none":
            errors.append("Execution authority changed: " + key)

    return errors


def verify_manifest(manifest: dict[str, str]) -> list[str]:
    errors: list[str] = []
    expected_paths = source_paths()

    if set(manifest) != expected_paths:
        missing = sorted(expected_paths - set(manifest))
        extra = sorted(set(manifest) - expected_paths)
        if missing:
            errors.append("Manifest missing source paths: " + ", ".join(missing))
        if extra:
            errors.append("Manifest contains extra paths: " + ", ".join(extra))

    for path, expected in manifest.items():
        actual = hashlib.sha256(
            tracked_blob(path, SOURCE_CLOSURE)
        ).hexdigest()
        if actual != expected:
            errors.append("Manifest checksum mismatch: " + path)

    return errors


def verify_lineage_and_patch() -> list[str]:
    errors: list[str] = []

    for ancestor, descendant, label in (
        (BASE_PHASE3, SOURCE_CLOSURE, "Phase III -> Model 2 source"),
        (
            SOURCE_CLOSURE,
            PREVIOUS_RELEASE_COMMIT,
            "source -> v1.0.0 metadata",
        ),
        (
            PREVIOUS_RELEASE_COMMIT,
            "HEAD",
            "v1.0.0 metadata -> current",
        ),
    ):
        completed = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            errors.append("Lineage failure: " + label)

    patch = observed_patch()
    if patch != PATCH_PATHS:
        missing = sorted(PATCH_PATHS - patch)
        extra = sorted(patch - PATCH_PATHS)
        if missing:
            errors.append("Compatibility patch missing: " + ", ".join(missing))
        if extra:
            errors.append(
                "Unexpected compatibility patch paths: " + ", ".join(extra)
            )

    commit_count = int(
        git_text(
            "rev-list",
            "--count",
            PREVIOUS_RELEASE_COMMIT + "..HEAD",
        )
    )

    working_delta = (
        names(git_text("diff", "--name-only"))
        | names(git_text("diff", "--cached", "--name-only"))
        | {
            path
            for path in names(
                git_text("ls-files", "--others", "--exclude-standard")
            )
            if not ignorable(path)
        }
    )

    if working_delta:
        if commit_count != 0:
            errors.append(
                "Pre-commit compatibility verification expects zero "
                "committed patch commits."
            )
    elif commit_count != 1:
        errors.append(
            "Frozen v1.0.1 compatibility release must be exactly one "
            "commit after v1.0.0 metadata; found "
            + str(commit_count)
            + "."
        )

    verifier = (
        ROOT / "scripts" / "verify_model2g_evaluation.py"
    ).read_text(encoding="utf-8")
    if 'branch = git("branch", "--show-current")' not in verifier:
        errors.append("2G verifier is not detached-HEAD aware.")
    if "if branch and branch != EXPECTED_BRANCH:" not in verifier:
        errors.append("2G detached-HEAD branch guard is not fail-closed.")

    return errors


def verify_previous_tag() -> list[str]:
    if not git_text("tag", "--list", PREVIOUS_TAG):
        return ["Missing immutable previous tag: " + PREVIOUS_TAG]

    target = git_text("rev-parse", PREVIOUS_TAG + "^{commit}")
    if target != PREVIOUS_RELEASE_COMMIT:
        return ["Immutable previous tag moved: " + PREVIOUS_TAG]
    return []


def verify_prerequisites() -> list[str]:
    errors: list[str] = []
    commands = (
        ["python", "scripts/verify_phase2_release.py", "--require-tag"],
        ["python", "scripts/verify_model1d_v038_release.py", "--require-tags"],
        ["python", "scripts/verify_phase3_evaluation.py"],
        ["python", "scripts/verify_phase3_release.py", "--require-tag"],
        ["python", "scripts/verify_model2g_evaluation.py"],
        ["python", "scripts/verify_model2h_production.py"],
    )
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            errors.append(
                "Prerequisite verifier failed: "
                + " ".join(command)
                + "\n"
                + completed.stdout
                + completed.stderr
            )
    return errors


def verify_no_runtime_artifacts() -> list[str]:
    bad: list[str] = []
    for raw in git_text("ls-files").splitlines():
        normalized = raw.replace("\\", "/").lower()
        if (
            normalized.startswith("data/backups/")
            or normalized.endswith(".duckdb")
            or normalized.endswith(".wal")
            or normalized.startswith(
                "reports/decision_intelligence_snapshots/"
            )
        ):
            bad.append(raw)
    return (
        []
        if not bad
        else ["Tracked runtime artifacts: " + ", ".join(bad)]
    )


def verify_tag(require_tag: bool) -> list[str]:
    matching = git_text("tag", "--list", TAG)
    if not matching:
        return (
            ["Required Model 2 release tag is missing: " + TAG]
            if require_tag
            else []
        )

    target = git_text("rev-parse", TAG + "^{commit}")
    head = git_text("rev-parse", "HEAD")
    if target != head:
        return [
            "Model 2 v1.0.1 release tag does not point to current "
            "compatibility-release commit."
        ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument(
        "--skip-prerequisite-verifiers",
        action="store_true",
    )
    args = parser.parse_args()

    errors: list[str] = []
    try:
        manifest = load_manifest()
        release = json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
        errors += verify_release_record(release, manifest)
        errors += verify_manifest(manifest)
        errors += verify_lineage_and_patch()
        errors += verify_previous_tag()
        errors += verify_no_runtime_artifacts()
        errors += verify_tag(args.require_tag)
        if not args.skip_prerequisite_verifiers:
            errors += verify_prerequisites()
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 2 BVAR v1.0.1 release verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2 BVAR v1.0.1 release verification: PASS")
    print(
        "Previous immutable tag: "
        + PREVIOUS_TAG
        + " -> "
        + PREVIOUS_RELEASE_COMMIT[:7]
    )
    print(
        "Prior tag-CI failure: Guard #15 / run "
        + str(FAILED_TAG_RUN)
        + " (detached-HEAD verifier contract only)"
    )
    print("Source closure: " + SOURCE_CLOSURE[:7])
    print(
        "Source CI gate: Model 2 Bayesian VAR Guard #"
        + str(SOURCE_CI_NUMBER)
        + " / run "
        + str(SOURCE_CI_RUN)
        + " PASS"
    )
    print("Manifest files verified: " + str(len(load_manifest())))
    print("Release patch type: tag-CI compatibility only")
    print("Semantic changes: none")
    print("Selected candidate: p=2 lambda=0.1 id=" + SELECTED_ID)
    print("Prospective retuning/switching: prohibited")
    print("Tracked runtime artifacts: none")
    if git_text("tag", "--list", TAG):
        print("Release tag: " + TAG + " -> current compatibility commit")
    else:
        print("Release tag: pending creation after v1.0.1 branch CI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

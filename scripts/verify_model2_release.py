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
COMPATIBILITY_SOURCE_COMMIT = "24f2a0f95984229f93635d33e5be315f72ed5d0d"

BASE_PHASE3 = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SOURCE_CI_RUN = 35769859027
SOURCE_CI_JOB = 106888547394
SOURCE_CI_NUMBER = 13

FAILED_TAG_RUN = 35775232829
FAILED_TAG_JOB = 106906660113
FAILED_BRANCH_CI_RUN = 35781569124
FAILED_BRANCH_CI_JOB = 106928064296

SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = (
    "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
)

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
    c = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=not binary,
    )
    if c.returncode != 0:
        out = c.stdout.decode(errors="replace") if binary else c.stdout
        err = c.stderr.decode(errors="replace") if binary else c.stderr
        raise RuntimeError(
            "git " + " ".join(args) + " failed:\n" + out + err
        )
    return c.stdout


def gt(*args: str) -> str:
    return str(git(*args)).strip()


def names(output: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def ignorable(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(p.startswith(prefix) for prefix in IGNORED_PREFIXES)


def governed_names(output: str) -> set[str]:
    return {path for path in names(output) if not ignorable(path)}


def blob(path: str, ref: str) -> bytes:
    return bytes(git("show", ref + ":" + path, binary=True))


def load_manifest() -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            digest, path = line.split("  ", 1)
            out[path] = digest
    return out


def source_paths() -> set[str]:
    return names(
        gt(
            "diff",
            "--diff-filter=ACMRT",
            "--name-only",
            BASE_PHASE3 + ".." + SOURCE_CLOSURE,
        )
    )


def observed_patch() -> set[str]:
    committed = names(
        gt(
            "diff",
            "--name-only",
            PREVIOUS_RELEASE_COMMIT + "..HEAD",
        )
    )
    working = governed_names(gt("diff", "--name-only"))
    staged = governed_names(gt("diff", "--cached", "--name-only"))
    untracked = governed_names(
        gt("ls-files", "--others", "--exclude-standard")
    )
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
    checks = {
        "workflow": "Model 2 Bayesian VAR Guard",
        "run_number": SOURCE_CI_NUMBER,
        "run_id": SOURCE_CI_RUN,
        "job_id": SOURCE_CI_JOB,
        "status": "completed",
        "conclusion": "success",
        "head_sha": SOURCE_CLOSURE,
    }
    for key, value in checks.items():
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

    tag_failure = release.get("prior_tag_ci_failure", {})
    if tag_failure.get("run_id") != FAILED_TAG_RUN:
        errors.append("Prior failed tag-CI run identity changed.")
    if tag_failure.get("job_id") != FAILED_TAG_JOB:
        errors.append("Prior failed tag-CI job identity changed.")
    if (
        tag_failure.get("failure_scope")
        != "release_verifier_contract_only"
    ):
        errors.append("Prior tag-CI failure classification changed.")
    if (
        tag_failure.get("model_or_forecast_semantics_affected")
        is not False
    ):
        errors.append("Prior tag-CI failure must remain non-semantic.")

    branch_failure = release.get("prior_branch_ci_failure", {})
    if branch_failure.get("head_sha") != COMPATIBILITY_SOURCE_COMMIT:
        errors.append("Prior failed branch-CI commit identity changed.")
    if branch_failure.get("run_id") != FAILED_BRANCH_CI_RUN:
        errors.append("Prior failed branch-CI run identity changed.")
    if branch_failure.get("job_id") != FAILED_BRANCH_CI_JOB:
        errors.append("Prior failed branch-CI job identity changed.")
    if (
        branch_failure.get("failure_scope")
        != "release_verifier_state_detection_only"
    ):
        errors.append("Prior branch-CI failure classification changed.")
    if (
        branch_failure.get("model_or_forecast_semantics_affected")
        is not False
    ):
        errors.append("Prior branch-CI failure must remain non-semantic.")

    lineage = release.get("release_engineering_lineage", {})
    if (
        lineage.get("v1_0_0_metadata_commit")
        != PREVIOUS_RELEASE_COMMIT
    ):
        errors.append("v1.0.0 metadata lineage changed.")
    if (
        lineage.get("v1_0_1_compatibility_source_commit")
        != COMPATIBILITY_SOURCE_COMMIT
    ):
        errors.append("v1.0.1 compatibility-source lineage changed.")
    if (
        lineage.get("final_state_detection_correction_commits_required")
        != 1
    ):
        errors.append("Final correction-count contract changed.")
    if lineage.get("model_or_forecast_semantics_changed") is not False:
        errors.append("Release-engineering lineage became semantic.")

    selected = release.get("selected_specification", {})
    if selected.get("candidate_id") != SELECTED_ID:
        errors.append("Released candidate ID changed.")
    if selected.get("lags") != 2:
        errors.append("Released lag order changed.")
    if abs(float(selected.get("shrinkage", -1.0)) - 0.1) > 1e-12:
        errors.append("Released shrinkage changed.")
    if selected.get("selection_evidence_payload_hash") != EVIDENCE_HASH:
        errors.append("Selection evidence identity changed.")

    scope = release.get("patch_scope", {})
    for key in (
        "model_logic",
        "forecast_semantics",
        "selected_specification",
        "structural_identification",
        "scenario_semantics",
        "pseudo_real_time_evidence",
        "source_manifest",
    ):
        if scope.get(key) != "unchanged":
            errors.append("Compatibility patch scope changed: " + key)

    if scope.get("tag_checkout_contract") != "detached_head_compatible":
        errors.append("Detached-HEAD compatibility scope changed.")
    if (
        scope.get("model2h_frozen_verifier_contract")
        != "permits_exact_model2g_detached_head_compatibility_only"
    ):
        errors.append("Model 2H compatibility contract changed.")

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
    expected = source_paths()

    if set(manifest) != expected:
        missing = sorted(expected - set(manifest))
        extra = sorted(set(manifest) - expected)
        if missing:
            errors.append("Manifest missing source paths: " + ", ".join(missing))
        if extra:
            errors.append("Manifest contains extra paths: " + ", ".join(extra))

    for path, digest in manifest.items():
        actual = hashlib.sha256(blob(path, SOURCE_CLOSURE)).hexdigest()
        if actual != digest:
            errors.append("Manifest checksum mismatch: " + path)

    return errors


def verify_ancestor(
    ancestor: str,
    descendant: str,
    label: str,
) -> list[str]:
    c = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [] if c.returncode == 0 else ["Lineage failure: " + label]


def verify_lineage_and_patch() -> list[str]:
    errors: list[str] = []

    errors += verify_ancestor(
        BASE_PHASE3,
        SOURCE_CLOSURE,
        "Phase III -> Model 2 source",
    )
    errors += verify_ancestor(
        SOURCE_CLOSURE,
        PREVIOUS_RELEASE_COMMIT,
        "Model 2 source -> v1.0.0 metadata",
    )
    errors += verify_ancestor(
        PREVIOUS_RELEASE_COMMIT,
        COMPATIBILITY_SOURCE_COMMIT,
        "v1.0.0 metadata -> v1.0.1 compatibility source",
    )
    errors += verify_ancestor(
        COMPATIBILITY_SOURCE_COMMIT,
        "HEAD",
        "v1.0.1 compatibility source -> current",
    )

    source_count = int(
        gt(
            "rev-list",
            "--count",
            PREVIOUS_RELEASE_COMMIT + ".." + COMPATIBILITY_SOURCE_COMMIT,
        )
    )
    if source_count != 1:
        errors.append(
            "Recorded v1.0.1 compatibility source must be exactly one "
            "commit after v1.0.0 metadata; found "
            + str(source_count)
            + "."
        )

    correction_count = int(
        gt(
            "rev-list",
            "--count",
            COMPATIBILITY_SOURCE_COMMIT + "..HEAD",
        )
    )

    working_delta = (
        governed_names(gt("diff", "--name-only"))
        | governed_names(gt("diff", "--cached", "--name-only"))
        | governed_names(
            gt("ls-files", "--others", "--exclude-standard")
        )
    )

    if working_delta:
        if correction_count != 0:
            errors.append(
                "Pre-correction verification expects zero committed "
                "correction commits after the recorded compatibility source."
            )
    elif correction_count != 1:
        errors.append(
            "Frozen v1.0.1 release must contain exactly one "
            "state-detection correction commit after the recorded "
            "compatibility source; found "
            + str(correction_count)
            + "."
        )

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

    verifier_2g = (
        ROOT / "scripts" / "verify_model2g_evaluation.py"
    ).read_text(encoding="utf-8")

    if 'branch = git("branch", "--show-current")' not in verifier_2g:
        errors.append("2G verifier is not detached-HEAD aware.")
    if "if branch and branch != EXPECTED_BRANCH:" not in verifier_2g:
        errors.append("2G detached-HEAD branch guard is not fail-closed.")

    verifier_2h = (
        ROOT / "scripts" / "verify_model2h_production.py"
    ).read_text(encoding="utf-8")

    if "expected_detached_head_2g_verifier" not in verifier_2h:
        errors.append(
            "2H verifier lost exact 2G compatibility enforcement."
        )
    if (
        "Exact Model 2G detached-HEAD compatibility: PASS"
        not in verifier_2h
    ):
        errors.append(
            "2H verifier lost detached-HEAD compatibility evidence."
        )

    return errors


def verify_previous_tag() -> list[str]:
    if not gt("tag", "--list", PREVIOUS_TAG):
        return ["Missing immutable previous tag: " + PREVIOUS_TAG]

    target = gt("rev-parse", PREVIOUS_TAG + "^{commit}")
    return (
        []
        if target == PREVIOUS_RELEASE_COMMIT
        else ["Immutable previous tag moved: " + PREVIOUS_TAG]
    )


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
        c = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if c.returncode != 0:
            errors.append(
                "Prerequisite verifier failed: "
                + " ".join(command)
                + "\n"
                + c.stdout
                + c.stderr
            )

    return errors


def verify_runtime() -> list[str]:
    bad: list[str] = []

    for raw in gt("ls-files").splitlines():
        p = raw.replace("\\", "/").lower()
        if (
            p.startswith("data/backups/")
            or p.endswith(".duckdb")
            or p.endswith(".wal")
            or p.startswith("reports/decision_intelligence_snapshots/")
        ):
            bad.append(raw)

    return [] if not bad else ["Tracked runtime artifacts: " + ", ".join(bad)]


def verify_tag(require: bool) -> list[str]:
    present = gt("tag", "--list", TAG)

    if not present:
        return (
            ["Required Model 2 release tag is missing: " + TAG]
            if require
            else []
        )

    target = gt("rev-parse", TAG + "^{commit}")
    head = gt("rev-parse", "HEAD")

    return (
        []
        if target == head
        else [
            "Model 2 v1.0.1 release tag does not point to current "
            "release-engineering commit."
        ]
    )


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
        errors += verify_runtime()
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
    print(
        "Prior branch-CI failure: Guard #16 / run "
        + str(FAILED_BRANCH_CI_RUN)
        + " (release-verifier state detection only)"
    )
    print(
        "Compatibility source commit: "
        + COMPATIBILITY_SOURCE_COMMIT[:7]
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

    if gt("tag", "--list", TAG):
        print("Release tag: " + TAG + " -> current release commit")
    else:
        print("Release tag: pending creation after v1.0.1 branch CI")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

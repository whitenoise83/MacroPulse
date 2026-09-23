from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_FILE = ROOT / "MODEL2_RELEASE.json"
MANIFEST_FILE = ROOT / "MANIFEST_MODEL2_v1.0.2.txt"

TAG = "model2-bvar-v1.0.2"
PREVIOUS_TAG = "model2-bvar-v1.0.1"
PREVIOUS_RELEASE_COMMIT = "7a54c19fe9216b2073b6bfc107ea5e4fc25bebd9"

BASE_PHASE3 = "edfc37b8f5f016710fb96402d205dcd35f2e09ca"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SOURCE_CI_RUN = 35769859027
SOURCE_CI_JOB = 106888547394
SOURCE_CI_NUMBER = 13

FAILED_TAG_RUN = 35822437102
FAILED_TAG_JOB = 107056962997
FAILED_TAG_RUN_NUMBER = 18

SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = (
    "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
)

PATCH_PATHS = {
    "MODEL2_RELEASE.json",
    "MANIFEST_MODEL2_v1.0.2.txt",
    "README_MODEL2_v1.0.2.md",
    "VALIDATION_MODEL2_v1.0.2.txt",
    "scripts/verify_model2_release.py",
    "tests/test_model2_release_metadata.py",
    "tests/test_model2a_bootstrap_contract.py",
    "tests/test_phase3_bootstrap_contract.py",
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
        raise RuntimeError("git " + " ".join(args) + " failed:\n" + out + err)
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


def ancestor(older: str, newer: str) -> bool:
    c = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return c.returncode == 0


def verify_release_record(
    release: dict,
    manifest: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    expected = {
        "roadmap_phase": "II",
        "model": "2",
        "model_name": "Bayesian VAR",
        "version": "1.0.2",
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
        errors.append("Previous release tag changed.")
    if previous.get("commit") != PREVIOUS_RELEASE_COMMIT:
        errors.append("Previous release commit changed.")
    if previous.get("immutable") is not True:
        errors.append("Previous v1.0.1 tag must remain immutable.")
    if previous.get("move_or_recreate") is not False:
        errors.append("Previous v1.0.1 tag movement policy changed.")
    if previous.get("tag_ci_run_id") != FAILED_TAG_RUN:
        errors.append("Previous v1.0.1 failed tag-CI run changed.")

    failure = release.get("prior_tag_ci_failure", {})
    if failure.get("release_tag") != PREVIOUS_TAG:
        errors.append("Prior failed tag identity changed.")
    if failure.get("head_sha") != PREVIOUS_RELEASE_COMMIT:
        errors.append("Prior failed tag commit changed.")
    if failure.get("run_id") != FAILED_TAG_RUN:
        errors.append("Prior failed tag-CI run identity changed.")
    if failure.get("job_id") != FAILED_TAG_JOB:
        errors.append("Prior failed tag-CI job identity changed.")
    if (
        failure.get("failure_scope")
        != "historical_bootstrap_test_checkout_contract_only"
    ):
        errors.append("Prior tag-CI failure classification changed.")
    if failure.get("model_or_forecast_semantics_affected") is not False:
        errors.append("Prior tag-CI failure must remain non-semantic.")
    if failure.get("model2_release_verifier_passed_before_failure") is not True:
        errors.append("Prior release-verifier PASS evidence changed.")
    if failure.get("model2_release_metadata_tests_passed_before_failure") is not True:
        errors.append("Prior release-metadata PASS evidence changed.")

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

    if (
        scope.get("historical_bootstrap_tests")
        != "descendant_and_detached_head_safe"
    ):
        errors.append("Historical bootstrap-test patch scope changed.")

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


def verify_lineage_and_patch() -> list[str]:
    errors: list[str] = []

    for older, newer, label in (
        (BASE_PHASE3, SOURCE_CLOSURE, "Phase III -> Model 2 source"),
        (
            SOURCE_CLOSURE,
            PREVIOUS_RELEASE_COMMIT,
            "Model 2 source -> v1.0.1 release",
        ),
        (
            PREVIOUS_RELEASE_COMMIT,
            "HEAD",
            "v1.0.1 release -> current",
        ),
    ):
        if not ancestor(older, newer):
            errors.append("Lineage failure: " + label)

    commit_count = int(
        gt(
            "rev-list",
            "--count",
            PREVIOUS_RELEASE_COMMIT + "..HEAD",
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
        if commit_count != 0:
            errors.append(
                "Pre-commit v1.0.2 verification expects zero committed "
                "patch commits after v1.0.1."
            )
    elif commit_count != 1:
        errors.append(
            "Frozen v1.0.2 release must be exactly one patch commit after "
            "v1.0.1; found " + str(commit_count) + "."
        )

    patch = observed_patch()
    if patch != PATCH_PATHS:
        missing = sorted(PATCH_PATHS - patch)
        extra = sorted(patch - PATCH_PATHS)
        if missing:
            errors.append("v1.0.2 patch missing: " + ", ".join(missing))
        if extra:
            errors.append(
                "Unexpected v1.0.2 patch paths: " + ", ".join(extra)
            )

    model2a = (
        ROOT / "tests" / "test_model2a_bootstrap_contract.py"
    ).read_text(encoding="utf-8")
    if 'git("branch", "--show-current") == BRANCH' in model2a:
        errors.append("Model 2A historical test still requires named branch.")

    phase3 = (
        ROOT / "tests" / "test_phase3_bootstrap_contract.py"
    ).read_text(encoding="utf-8")
    if "RELEASE_TAG_PATTERN" in phase3:
        errors.append("Phase III historical test still requires tag-at-HEAD.")
    if (
        '"merge-base",' not in phase3
        or '"--is-ancestor",' not in phase3
        or "EXPECTED_FINAL_RELEASE_COMMIT" not in phase3
    ):
        errors.append("Phase III historical descendant check is missing.")

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
        return ["Required Model 2 release tag is missing: " + TAG] if require else []

    target = gt("rev-parse", TAG + "^{commit}")
    head = gt("rev-parse", "HEAD")
    return (
        []
        if target == head
        else ["Model 2 v1.0.2 release tag does not point to current release commit."]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument("--skip-prerequisite-verifiers", action="store_true")
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
        print("Model 2 BVAR v1.0.2 release verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 2 BVAR v1.0.2 release verification: PASS")
    print("Previous immutable tag: " + PREVIOUS_TAG + " -> " + PREVIOUS_RELEASE_COMMIT[:7])
    print(
        "Prior tag-CI failure: Guard #"
        + str(FAILED_TAG_RUN_NUMBER)
        + " / run "
        + str(FAILED_TAG_RUN)
        + " (historical bootstrap checkout contract only)"
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
    print("Historical bootstrap tests: descendant/tag-checkout safe")
    print("Tracked runtime artifacts: none")
    if gt("tag", "--list", TAG):
        print("Release tag: " + TAG + " -> current release commit")
    else:
        print("Release tag: pending creation after v1.0.2 branch CI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

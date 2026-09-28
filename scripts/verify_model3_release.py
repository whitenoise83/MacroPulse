from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TAG = "model3-potential-output-v1.0.0"
PREDECESSOR_TAG = "model3-pseudo-real-time-v1.0.0"
PREDECESSOR_COMMIT = "a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094"
SOURCE_HARDENING = "568b1302d4406736e5568371d7354c6ce10bcbb6"
PRE_RELEASE_CLOSURE = "c018b4771108bbc646614d61f1970f4e55e4544a"
PRE_RELEASE_CI_RUN = 36425589715
PRE_RELEASE_CI_NUMBER = 6

RELEASE_FILE = ROOT / "MODEL3_RELEASE.json"
MANIFEST_FILE = ROOT / "MANIFEST_MODEL3_v1.0.0.txt"

RELEASE_PATHS = {
    "MODEL3_RELEASE.json",
    "MANIFEST_MODEL3_v1.0.0.txt",
    "README_MODEL3_v1.0.0.md",
    "VALIDATION_MODEL3_v1.0.0.txt",
    "scripts/verify_model3_release.py",
    "tests/test_model3_release_metadata.py",
}

IGNORED_PREFIXES = (
    "src/macropulse.egg-info/",
    "reports/inflation_operational_validation/",
    "reports/labour_operational_validation/",
    "reports/model3h_final_evaluation/",
    "reports/model3h_pseudo_real_time/",
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


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def source_paths() -> set[str]:
    raw = gt("ls-tree", "-r", "--name-only", PRE_RELEASE_CLOSURE)
    result: set[str] = set()
    for path in raw.splitlines():
        p = path.replace("\\", "/")
        include = (
            p in {
                ".github/workflows/model3-potential-output-guard.yml",
                "MACROPULSE_MODEL3_PLAN.md",
                "app.py",
                "pyproject.toml",
                "ui/model3_slack.py",
            }
            or (p.startswith("MODEL3") and p.endswith(".json"))
            or (p.startswith("docs/MODEL3") and p.endswith(".md"))
            or p.startswith("reports/model3h_")
            or p.startswith("reports/model3i_release_audits/")
            or (
                p.startswith("scripts/")
                and "model3" in p.lower()
                and p.endswith(".py")
            )
            or p.startswith("src/macropulse/slack/")
            or (
                p.startswith("tests/test_model3")
                and p.endswith(".py")
            )
        )
        if include:
            result.add(p)
    return result


def blob(path: str, ref: str) -> bytes:
    return bytes(git("show", ref + ":" + path, binary=True))


def load_manifest() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        digest, path = line.split("  ", 1)
        result[path] = digest
    return result


def ancestor(older: str, newer: str) -> bool:
    c = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return c.returncode == 0


def ignorable(path: str) -> bool:
    p = path.replace("\\", "/")
    return any(p.startswith(prefix) for prefix in IGNORED_PREFIXES)


def working_delta() -> set[str]:
    paths: set[str] = set()
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    for command in commands:
        for raw in gt(*command).splitlines():
            p = raw.strip().replace("\\", "/")
            if p and not ignorable(p):
                paths.add(p)
    return paths


def observed_release_patch() -> set[str]:
    head = gt("rev-parse", "HEAD")
    if head == PRE_RELEASE_CLOSURE:
        return working_delta()
    parent = gt("rev-parse", "HEAD^")
    if parent != PRE_RELEASE_CLOSURE:
        return set()
    return {
        p.strip().replace("\\", "/")
        for p in gt("diff", "--name-only", PRE_RELEASE_CLOSURE + "..HEAD").splitlines()
        if p.strip()
    }


def verify_release_record(release: dict, manifest: dict[str, str]) -> list[str]:
    errors: list[str] = []
    checks = (
        (release.get("roadmap_phase") == "II", "Roadmap phase must be II."),
        (release.get("model") == "3", "Model identity must be 3."),
        (
            release.get("model_name") == "Potential Output & Macroeconomic Slack",
            "Model name changed.",
        ),
        (release.get("version") == "1.0.0", "Version must be 1.0.0."),
        (release.get("release_tag") == TAG, "Release tag changed."),
        (
            release.get("selected_candidate", {}).get("candidate_id") == "3D",
            "Selected candidate must remain 3D.",
        ),
        (
            release.get("predecessor", {}).get("tag") == PREDECESSOR_TAG,
            "Predecessor tag changed.",
        ),
        (
            release.get("predecessor", {}).get("commit") == PREDECESSOR_COMMIT,
            "Predecessor commit changed.",
        ),
        (
            release.get("source_hardening_closure", {}).get("commit")
            == SOURCE_HARDENING,
            "Source-hardening closure changed.",
        ),
        (
            release.get("pre_release_closure", {}).get("commit")
            == PRE_RELEASE_CLOSURE,
            "Pre-release closure changed.",
        ),
        (
            release.get("pre_release_closure", {}).get("ci", {}).get("run_id")
            == PRE_RELEASE_CI_RUN,
            "Pre-release CI run changed.",
        ),
        (
            release.get("pre_release_closure", {}).get("ci", {}).get("conclusion")
            == "success",
            "Pre-release CI must be successful.",
        ),
        (
            release.get("manifest_file") == MANIFEST_FILE.name,
            "Manifest filename changed.",
        ),
        (
            release.get("manifest_file_count") == len(manifest),
            "Manifest file count changed.",
        ),
        (
            release.get("manifest_sha256") == canonical_text_sha256(MANIFEST_FILE),
            "Manifest SHA-256 changed.",
        ),
    )
    for ok, message in checks:
        if not ok:
            errors.append(message)

    governance = release.get("governance", {})
    for key in (
        "candidate_specification_immutable",
        "econometric_retuning_prohibited",
        "automatic_switching_prohibited",
        "model1_mutation_prohibited",
        "model2_mutation_prohibited",
        "model4_performance_selection_prohibited",
        "model1d_validation_selection_gate_prohibited",
        "generative_ai_in_governed_core_prohibited",
    ):
        if governance.get(key) is not True:
            errors.append("Release governance changed: " + key)

    semantics = release.get("production_semantics", {})
    if semantics.get("current_estimate_class") != "production_current_endpoint":
        errors.append("Current estimate class changed.")
    if semantics.get("revised_history_class") != "smoothed_revised":
        errors.append("Revised history class changed.")
    if semantics.get("full_sample_filtered_history_claimed_real_time") is not False:
        errors.append("Full-sample filtered history may not be claimed real time.")

    fwd = release.get("forward_gap_semantics", {})
    if fwd.get("potential_continuation") != "deterministic":
        errors.append("Forward potential continuation semantics changed.")
    if fwd.get("potential_uncertainty_claimed") is not False:
        errors.append("Release may not claim forward potential uncertainty.")

    revision = release.get("revision_disclosure", {})
    if revision.get("selection_reopened") is not False:
        errors.append("Revision audit may not reopen selection.")
    if revision.get("post_hoc_cutoff_introduced") is not False:
        errors.append("Post-hoc revision cutoff is prohibited.")

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
        actual = hashlib.sha256(blob(path, PRE_RELEASE_CLOSURE)).hexdigest()
        if actual != digest:
            errors.append("Manifest checksum mismatch: " + path)
    return errors


def verify_lineage_and_patch() -> list[str]:
    errors: list[str] = []
    for older, newer, label in (
        (PREDECESSOR_COMMIT, SOURCE_HARDENING, "3H -> source hardening"),
        (SOURCE_HARDENING, PRE_RELEASE_CLOSURE, "source hardening -> pre-release closure"),
        (PRE_RELEASE_CLOSURE, "HEAD", "pre-release closure -> current"),
    ):
        if not ancestor(older, newer):
            errors.append("Lineage failure: " + label)

    head = gt("rev-parse", "HEAD")
    patch = observed_release_patch()
    if patch != RELEASE_PATHS:
        missing = sorted(RELEASE_PATHS - patch)
        extra = sorted(patch - RELEASE_PATHS)
        if missing:
            errors.append("Release patch missing: " + ", ".join(missing))
        if extra:
            errors.append("Unexpected release patch paths: " + ", ".join(extra))

    if head != PRE_RELEASE_CLOSURE:
        if gt("rev-parse", "HEAD^") != PRE_RELEASE_CLOSURE:
            errors.append("Final release metadata commit must be a direct child of pre-release closure.")
        if working_delta():
            errors.append(
                "Committed release verification requires no non-ignored working-tree delta."
            )
    return errors


def verify_predecessor_tag() -> list[str]:
    if not gt("tag", "--list", PREDECESSOR_TAG):
        return ["Missing immutable predecessor tag: " + PREDECESSOR_TAG]
    target = gt("rev-parse", PREDECESSOR_TAG + "^{commit}")
    return [] if target == PREDECESSOR_COMMIT else [
        "Immutable predecessor tag moved: " + PREDECESSOR_TAG
    ]


def verify_tag(require: bool) -> list[str]:
    present = gt("tag", "--list", TAG)
    if not present:
        return ["Required Model 3 release tag is missing: " + TAG] if require else []

    target = gt("rev-parse", TAG + "^{commit}")
    head = gt("rev-parse", "HEAD")
    if target != head:
        return ["Model 3 release tag does not point to current release commit."]
    if head == PRE_RELEASE_CLOSURE:
        return ["Model 3 release tag may not point to the pre-release closure."]
    return []


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tag", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        release = json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
        manifest = load_manifest()
        errors += verify_release_record(release, manifest)
        errors += verify_manifest(manifest)
        errors += verify_lineage_and_patch()
        errors += verify_predecessor_tag()
        errors += verify_runtime()
        errors += verify_tag(args.require_tag)
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("Model 3 Potential Output v1.0.0 release verification: FAIL")
        for error in errors:
            print("- " + error)
        return 1

    print("Model 3 Potential Output v1.0.0 release verification: PASS")
    print("Predecessor: " + PREDECESSOR_TAG + " -> " + PREDECESSOR_COMMIT[:7])
    print("Source-hardening closure: " + SOURCE_HARDENING[:7])
    print(
        "Pre-release closure: "
        + PRE_RELEASE_CLOSURE[:7]
        + " | Guard #"
        + str(PRE_RELEASE_CI_NUMBER)
        + " / run "
        + str(PRE_RELEASE_CI_RUN)
        + " PASS"
    )
    print("Selected candidate: 3D")
    print("Manifest files verified: " + str(len(load_manifest())))
    print("Production current class: production_current_endpoint")
    print("Revised history class: smoothed_revised")
    print("Forward potential continuation: deterministic / no potential uncertainty claim")
    print("Tracked runtime artifacts: none")
    if gt("tag", "--list", TAG):
        print("Release tag: " + TAG + " -> current release commit")
    else:
        print("Release tag: pending creation after release-metadata branch CI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

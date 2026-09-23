from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "MODEL2_RELEASE.json"
MANIFEST = ROOT / "MANIFEST_MODEL2_v1.0.2.txt"

PREVIOUS_TAG = "model2-bvar-v1.0.1"
PREVIOUS_COMMIT = "7a54c19fe9216b2073b6bfc107ea5e4fc25bebd9"
NEW_TAG = "model2-bvar-v1.0.2"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = (
    "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
)


def load_release() -> dict:
    return json.loads(RELEASE.read_text(encoding="utf-8"))


def manifest_entries() -> dict[str, str]:
    result = {}
    for raw in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            digest, path = line.split("  ", 1)
            result[path] = digest
    return result


def canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def test_release_identity_is_v102_compatibility_patch() -> None:
    value = load_release()
    assert value["roadmap_phase"] == "II"
    assert value["model"] == "2"
    assert value["model_name"] == "Bayesian VAR"
    assert value["version"] == "1.0.2"
    assert value["release_tag"] == NEW_TAG
    assert value["release_type"] == "release_engineering_patch"
    assert value["semantic_change"] is False


def test_previous_v101_tag_is_recorded_immutable() -> None:
    previous = load_release()["previous_release"]
    assert previous["tag"] == PREVIOUS_TAG
    assert previous["commit"] == PREVIOUS_COMMIT
    assert previous["immutable"] is True
    assert previous["move_or_recreate"] is False
    assert previous["tag_ci_run_id"] == 35822437102
    assert previous["tag_ci_job_id"] == 107056962997


def test_prior_v101_tag_ci_failure_is_non_semantic() -> None:
    failure = load_release()["prior_tag_ci_failure"]
    assert failure["run_id"] == 35822437102
    assert failure["job_id"] == 107056962997
    assert failure["head_sha"] == PREVIOUS_COMMIT
    assert (
        failure["failure_scope"]
        == "historical_bootstrap_test_checkout_contract_only"
    )
    assert failure["model_or_forecast_semantics_affected"] is False
    assert failure["model2_release_verifier_passed_before_failure"] is True
    assert (
        failure["model2_release_metadata_tests_passed_before_failure"]
        is True
    )


def test_source_and_selected_specification_unchanged() -> None:
    value = load_release()
    assert value["source_closure"]["commit"] == SOURCE_CLOSURE
    selected = value["selected_specification"]
    assert selected["candidate_id"] == SELECTED_ID
    assert selected["lags"] == 2
    assert selected["shrinkage"] == 0.1
    assert selected["selection_evidence_payload_hash"] == EVIDENCE_HASH


def test_manifest_hash_matches_release_record() -> None:
    value = load_release()
    assert (
        value["manifest_sha256"]
        == canonical_text_sha256(MANIFEST)
    )
    assert value["manifest_file_count"] == len(manifest_entries())


def test_manifest_hashes_frozen_source_closure_blobs() -> None:
    for path, expected in manifest_entries().items():
        completed = subprocess.run(
            ["git", "show", SOURCE_CLOSURE + ":" + path],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        assert hashlib.sha256(completed.stdout).hexdigest() == expected


def test_v102_release_verifier_is_tag_optional_before_creation() -> None:
    completed = subprocess.run(
        [
            "python",
            "scripts/verify_model2_release.py",
            "--skip-prerequisite-verifiers",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_model2a_historical_test_does_not_require_physical_branch() -> None:
    text = (
        ROOT / "tests" / "test_model2a_bootstrap_contract.py"
    ).read_text(encoding="utf-8")
    assert 'git("branch", "--show-current") == BRANCH' not in text
    assert 'data["branch"] == BRANCH' in text


def test_phase3_historical_test_is_descendant_safe() -> None:
    text = (
        ROOT / "tests" / "test_phase3_bootstrap_contract.py"
    ).read_text(encoding="utf-8")
    assert "RELEASE_TAG_PATTERN" not in text
    assert '"merge-base",' in text
    assert '"--is-ancestor",' in text
    assert "EXPECTED_FINAL_RELEASE_COMMIT" in text


def test_v102_branch_ci_line_ending_failure_is_recorded_non_semantic() -> None:
    value = load_release()
    failure = value["prior_v1_0_2_branch_ci_failure"]
    assert failure["run_id"] == 35828571469
    assert failure["job_id"] == 107075679760
    assert failure["head_sha"] == "320bc8b5db7c6b4f86b1de5318f6616277689af9"
    assert failure["failure_scope"] == "manifest_line_ending_hash_only"
    assert failure["model_or_forecast_semantics_affected"] is False
    assert value["patch_scope"]["manifest_hash_contract"] == "utf8_lf_normalized_sha256"
    assert value["release_engineering_lineage"]["v1_0_2_patch_commits_required"] == 2

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "MODEL2_RELEASE.json"
MANIFEST = ROOT / "MANIFEST_MODEL2_v1.0.1.txt"

PREVIOUS_TAG = "model2-bvar-v1.0.0"
PREVIOUS_COMMIT = "22664c1d3a102ce88b62966dfb6c1f8a3405023f"
NEW_TAG = "model2-bvar-v1.0.1"
SOURCE_CLOSURE = "df1da2bcd54cf71277eb8bfe21f6c52caad1c302"
SELECTED_ID = "a69878bf644615c5"
EVIDENCE_HASH = "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"


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


def test_release_identity_is_v101_compatibility_patch() -> None:
    value = load_release()
    assert value["roadmap_phase"] == "II"
    assert value["model"] == "2"
    assert value["model_name"] == "Bayesian VAR"
    assert value["version"] == "1.0.1"
    assert value["release_tag"] == NEW_TAG
    assert value["release_type"] == "release_engineering_patch"
    assert value["semantic_change"] is False


def test_previous_v100_tag_is_recorded_immutable() -> None:
    previous = load_release()["previous_release"]
    assert previous["tag"] == PREVIOUS_TAG
    assert previous["commit"] == PREVIOUS_COMMIT
    assert previous["immutable"] is True
    assert previous["move_or_recreate"] is False


def test_prior_tag_ci_failure_is_non_semantic() -> None:
    failure = load_release()["prior_tag_ci_failure"]
    assert failure["run_id"] == 35775232829
    assert failure["job_id"] == 106906660113
    assert failure["failure_scope"] == "release_verifier_contract_only"
    assert failure["model_or_forecast_semantics_affected"] is False


def test_source_and_selected_specification_unchanged() -> None:
    value = load_release()
    assert value["source_closure"]["commit"] == SOURCE_CLOSURE
    selected = value["selected_specification"]
    assert selected["candidate_id"] == SELECTED_ID
    assert selected["lags"] == 2
    assert selected["shrinkage"] == 0.1
    assert (
        selected["selection_evidence_payload_hash"]
        == EVIDENCE_HASH
    )


def test_manifest_hash_matches_release_record() -> None:
    value = load_release()
    assert (
        value["manifest_sha256"]
        == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
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


def test_model2g_verifier_is_detached_head_compatible() -> None:
    text = (
        ROOT / "scripts" / "verify_model2g_evaluation.py"
    ).read_text(encoding="utf-8")
    assert 'branch = git("branch", "--show-current")' in text
    assert "if branch and branch != EXPECTED_BRANCH:" in text


def test_v101_release_verifier_is_tag_optional_before_creation() -> None:
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

def test_model2h_verifier_enforces_exact_2g_compatibility() -> None:
    text = (
        ROOT / "scripts" / "verify_model2h_production.py"
    ).read_text(encoding="utf-8")
    assert "expected_detached_head_2g_verifier" in text
    assert "Exact Model 2G detached-HEAD compatibility: PASS" in text

def test_prior_branch_ci_failure_is_recorded_non_semantic() -> None:
    failure = load_release()["prior_branch_ci_failure"]
    assert failure["run_id"] == 35781569124
    assert failure["job_id"] == 106928064296
    assert failure["head_sha"] == (
        "24f2a0f95984229f93635d33e5be315f72ed5d0d"
    )
    assert (
        failure["failure_scope"]
        == "release_verifier_state_detection_only"
    )
    assert (
        failure["model_or_forecast_semantics_affected"]
        is False
    )

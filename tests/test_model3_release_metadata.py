from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "MODEL3_RELEASE.json"
MANIFEST = ROOT / "MANIFEST_MODEL3_v1.0.0.txt"

TAG = "model3-potential-output-v1.0.0"
PREDECESSOR_TAG = "model3-pseudo-real-time-v1.0.0"
PREDECESSOR_COMMIT = "a8ebf2d05a3b49d0c21f5ab1b03ca6eefca0b094"
SOURCE_HARDENING = "568b1302d4406736e5568371d7354c6ce10bcbb6"
PRE_RELEASE_CLOSURE = "c018b4771108bbc646614d61f1970f4e55e4544a"


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


def test_release_identity() -> None:
    value = load_release()
    assert value["roadmap_phase"] == "II"
    assert value["model"] == "3"
    assert value["model_name"] == "Potential Output & Macroeconomic Slack"
    assert value["version"] == "1.0.0"
    assert value["release_tag"] == TAG
    assert value["selected_candidate"]["candidate_id"] == "3D"


def test_frozen_lineage_is_recorded() -> None:
    value = load_release()
    assert value["predecessor"]["tag"] == PREDECESSOR_TAG
    assert value["predecessor"]["commit"] == PREDECESSOR_COMMIT
    assert value["predecessor"]["immutable"] is True
    assert value["source_hardening_closure"]["commit"] == SOURCE_HARDENING
    assert value["pre_release_closure"]["commit"] == PRE_RELEASE_CLOSURE
    assert value["pre_release_closure"]["ci"]["run_id"] == 36425589715
    assert value["pre_release_closure"]["ci"]["run_number"] == 6
    assert value["pre_release_closure"]["ci"]["conclusion"] == "success"


def test_production_semantics_are_explicit() -> None:
    value = load_release()
    semantics = value["production_semantics"]
    assert semantics["current_estimate_class"] == "production_current_endpoint"
    assert semantics["revised_history_class"] == "smoothed_revised"
    assert semantics["full_sample_filtered_history_claimed_real_time"] is False
    forward = value["forward_gap_semantics"]
    assert forward["potential_continuation"] == "deterministic"
    assert forward["potential_uncertainty_claimed"] is False


def test_revision_disclosure_preserves_selection() -> None:
    value = load_release()["revision_disclosure"]
    assert value["selection_reopened"] is False
    assert value["post_hoc_cutoff_introduced"] is False
    assert abs(value["latest_revision_maxabs_pp"] - 3.7976052138173344) < 1e-12
    assert abs(value["per_quarter_max_revision_max_pp"] - 4.702237452099567) < 1e-12


def test_manifest_hash_matches_release_record() -> None:
    value = load_release()
    assert value["manifest_sha256"] == canonical_text_sha256(MANIFEST)
    assert value["manifest_file_count"] == len(manifest_entries())


def test_manifest_hashes_pre_release_closure_blobs() -> None:
    for path, expected in manifest_entries().items():
        completed = subprocess.run(
            ["git", "show", PRE_RELEASE_CLOSURE + ":" + path],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        assert hashlib.sha256(completed.stdout).hexdigest() == expected


def test_release_verifier_is_tag_optional_before_creation() -> None:
    completed = subprocess.run(
        ["python", "scripts/verify_model3_release.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_governance_prohibitions_are_frozen() -> None:
    g = load_release()["governance"]
    assert g["candidate_specification_immutable"] is True
    assert g["econometric_retuning_prohibited"] is True
    assert g["automatic_switching_prohibited"] is True
    assert g["model1_mutation_prohibited"] is True
    assert g["model2_mutation_prohibited"] is True
    assert g["model4_performance_selection_prohibited"] is True
    assert g["model1d_validation_selection_gate_prohibited"] is True
    assert g["generative_ai_in_governed_core_prohibited"] is True

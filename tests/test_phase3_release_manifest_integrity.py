from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
VERIFIER_PATH = ROOT / "scripts" / "verify_phase3_release.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("phase3_release_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase3_release_manifest_integrity() -> None:
    verifier = load_verifier()
    manifest = verifier.load_manifest()
    assert len(manifest) > 0
    assert verifier.MANIFEST_FILE.name not in manifest
    assert verifier.verify_manifest(manifest) == []


def test_phase3_release_record_matches_manifest() -> None:
    verifier = load_verifier()
    release = verifier.load_release()
    manifest = verifier.load_manifest()
    assert verifier.verify_release_record(release, manifest) == []


def test_phase3_release_source_identity_is_valid() -> None:
    verifier = load_verifier()
    manifest = verifier.load_manifest()
    assert verifier.verify_source_identity(manifest) == []


def test_phase3_release_has_no_tracked_runtime_artifacts() -> None:
    verifier = load_verifier()
    assert verifier.verify_no_tracked_runtime_artifacts() == []


def test_phase3_release_workflow_has_branch_and_tag_gates() -> None:
    text = (ROOT / ".github/workflows/phase3-evaluation-guard.yml").read_text(encoding="utf-8")
    assert "Verify Phase III release record when present" in text
    assert "verify_phase3_release.py" in text
    assert "verify_phase3_release.py --require-tag" in text
    assert "github.ref_type == 'tag'" in text

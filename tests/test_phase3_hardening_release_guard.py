from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
VERIFIER = ROOT / "scripts" / "verify_phase3_evaluation.py"

def load_verifier():
    spec = importlib.util.spec_from_file_location("phase3_hardening_verifier", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_phase3_boundary_hardening_verifier_passes() -> None:
    module = load_verifier()
    assert module.verify_boundary(ROOT) == []

def test_phase3_descends_from_immutable_phase2_release() -> None:
    module = load_verifier()
    assert module.verify_phase2_ancestry(ROOT) == []

def test_phase3_changes_are_isolated_from_model_implementation() -> None:
    module = load_verifier()
    assert module.verify_phase3_change_isolation(ROOT) == []

def test_phase3_required_hardening_files_exist() -> None:
    module = load_verifier()
    assert module.verify_required_files(ROOT) == []

def test_phase3_tracks_no_runtime_evaluation_artifacts() -> None:
    module = load_verifier()
    assert module.verify_no_tracked_runtime_artifacts(ROOT) == []

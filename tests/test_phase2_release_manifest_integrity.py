from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
VERIFIER = ROOT / "scripts" / "verify_phase2_release.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location(
        "phase2_release_verifier",
        VERIFIER,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_phase2_release_manifest_integrity() -> None:
    module = load_verifier()
    assert module.verify_manifest(ROOT) == []


def test_phase2_release_metadata_integrity() -> None:
    module = load_verifier()
    assert module.verify_metadata(ROOT) == []


def test_phase2_release_descends_from_successful_ci_base() -> None:
    module = load_verifier()
    assert module.verify_source_ancestry(ROOT) == []

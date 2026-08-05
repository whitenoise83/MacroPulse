from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "verify_model1d_v038_release.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location("model1d_v038_release_verifier", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_verifier_files_are_present() -> None:
    assert SCRIPT.is_file()
    workflow = ROOT / ".github" / "workflows" / "model1d-v038-release-guard.yml"
    assert workflow.is_file()


def test_manifest_hashes_match_using_cross_platform_canonicalisation() -> None:
    verifier = load_verifier()
    checked = verifier.verify_manifest_hashes()
    assert "MODEL1D_v0.3.8_RELEASE.json" in checked
    assert "config/macro_state_governance.yml" in checked
    assert "docs/MODEL1D_v0.3.8_OPERATIONS.md" in checked


def test_release_boundary_remains_research_only() -> None:
    verifier = load_verifier()
    verifier.verify_release_boundary()

    release = json.loads(
        (ROOT / "MODEL1D_v0.3.8_RELEASE.json").read_text(encoding="utf-8")
    )
    assert release["promotion_authority"] == "none"
    assert release["promotion_approved"] is False
    assert release["switching_approved"] is False
    assert release["blending_approved"] is False
    assert release["source_replacement_approved"] is False


def test_workflow_uses_complete_history_and_explicit_python() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "model1d-v038-release-guard.yml"
    ).read_text(encoding="utf-8")
    assert "actions/checkout@v7" in workflow
    assert "fetch-depth: 0" in workflow
    assert "actions/setup-python@v7" in workflow
    assert 'python-version: "3.11"' in workflow
    assert (
        workflow.count(
            "python scripts/verify_model1d_v038_release.py --require-tags"
        )
        == 2
    )
    assert "python -m pytest -q --disable-warnings" in workflow
    assert "git status --porcelain --untracked-files=no" not in workflow


def test_no_prohibited_database_artifacts_are_tracked() -> None:
    verifier = load_verifier()
    verifier.verify_no_database_artifacts_tracked()

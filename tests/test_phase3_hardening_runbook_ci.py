from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNBOOK = ROOT / "docs" / "PHASE3_OPERATIONAL_RUNBOOK.md"
WORKFLOW = ROOT / ".github" / "workflows" / "phase3-evaluation-guard.yml"

def test_runbook_preserves_first_release_and_model1d_boundaries() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "latest/revised" in text
    assert "Model 1D remains a separate prospective research path." in text
    assert "promotion authority: none" in text

def test_phase3_ci_guard_runs_frozen_release_verifiers() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "verify_phase2_release.py --require-tag" in text
    assert "verify_model1d_v038_release.py --require-tags" in text
    assert "verify_phase3_evaluation.py" in text
    assert "tests/test_phase3*.py" in text
    assert "python -m pytest -q --disable-warnings" in text

def test_phase3_ci_guard_has_full_history_and_tag_trigger() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "fetch-depth: 0" in text
    assert 'phase3-evaluation-v*' in text

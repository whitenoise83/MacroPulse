from __future__ import annotations

from pathlib import Path

from macropulse.macro_state.versioning import load_macro_state_governance


def test_governed_minimum_evidence_and_no_promotion() -> None:
    config = load_macro_state_governance()
    section = config["prospective_transition_shadow"]
    assert section["minimum_evidence"]["complete_target_months"] == 12
    assert section["promotion_authority"] == "none"
    assert section["comparator"]["adaptive_switching_prohibited"] is True
    assert section["comparator"]["blending_prohibited"] is True


def test_phase4_operational_modules_do_not_modify_shadow_tables() -> None:
    root = Path(__file__).parents[1]
    paths = [
        root / "src" / "macropulse" / "operations" / "model1d_shadow_monitoring.py",
        root / "src" / "macropulse" / "operations" / "model1d_shadow_operations.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    assert "update macro_state_shadow" not in combined
    assert "delete from macro_state_shadow" not in combined
    assert "insert into macro_state_shadow" not in combined


def test_shadow_dashboard_is_read_only_and_registered() -> None:
    root = Path(__file__).parents[1]
    page = (root / "ui" / "macro_state_shadow.py").read_text(encoding="utf-8")
    app = (root / "app.py").read_text(encoding="utf-8")
    assert "run_macro_state_prospective_shadow" not in page
    assert "resolve_macro_state_shadow_outcomes" not in page
    assert 'st.Page("ui/macro_state_shadow.py"' in app

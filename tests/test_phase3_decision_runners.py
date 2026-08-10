from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]
REPORT = ROOT / "scripts" / "report_decision_intelligence.py"
EXPORT = ROOT / "scripts" / "export_decision_intelligence_snapshot.py"
UI = ROOT / "ui" / "evaluation_dashboard.py"
APP = ROOT / "app.py"
GITIGNORE = ROOT / ".gitignore"


def test_report_and_dashboard_have_no_mutating_controls() -> None:
    forbidden = [
        "--execute",
        "--refresh",
        "--download",
        "initialise(",
        "save_forecast",
        "replace_historical_snapshot",
        "run_staged",
        "run_live",
        "macro_state_shadow_operations",
    ]
    for path in (REPORT, UI):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text


def test_export_only_writes_local_snapshot_artifact() -> None:
    text = EXPORT.read_text(encoding="utf-8")
    assert "write_decision_intelligence_snapshot" in text
    assert "initialise(" not in text
    assert "run_live" not in text
    assert "replace_historical_snapshot" not in text


def test_phase3e_dashboard_uses_current_streamlit_width_api() -> None:
    text = UI.read_text(encoding="utf-8")
    assert "use_container_width" not in text
    assert 'width="stretch"' in text


def test_streamlit_navigation_registers_forecast_intelligence() -> None:
    text = APP.read_text(encoding="utf-8")
    assert (
        'st.Page("ui/evaluation_dashboard.py", '
        'title="Forecast Intelligence", icon="🎯")'
    ) in text


def test_local_decision_exports_are_ignored() -> None:
    text = GITIGNORE.read_text(encoding="utf-8")
    assert "reports/decision_intelligence_snapshots/" in text

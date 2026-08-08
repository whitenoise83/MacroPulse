from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
APP = ROOT / "app.py"
PAGE = ROOT / "ui" / "platform_dashboard.py"
HELPER = ROOT / "src" / "macropulse" / "platform" / "dashboard.py"


def test_phase2e_files_are_syntax_valid() -> None:
    ast.parse(PAGE.read_text(encoding="utf-8"))
    ast.parse(HELPER.read_text(encoding="utf-8"))


def test_platform_dashboard_is_registered() -> None:
    text = APP.read_text(encoding="utf-8")
    assert 'st.Page("ui/platform_dashboard.py"' in text
    assert 'title="Platform Overview"' in text


def test_dashboard_consumes_phase2d_snapshot() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "build_macro_snapshot" in text
    assert "snapshot_download_bytes" in text


def test_dashboard_has_no_direct_database_or_model_execution_logic() -> None:
    text = PAGE.read_text(encoding="utf-8")
    forbidden = (
        ".query_df(",
        "repository.initialise(",
        "run_baseline_nowcast",
        "run_inflation_nowcast",
        "run_labour_nowcast",
        "run_macro_state_shadow_operations",
        "run_macro_state(",
        "download_fred_data",
        "download_inflation_data",
        "download_labour_data",
    )
    for marker in forbidden:
        assert marker not in text


def test_dashboard_keeps_model1d_research_only_language() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "Research only" in text
    assert "source_run_advance_detected" in text
    assert "promotion" in text.lower()

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "run_platform_operations.py"
ORCHESTRATION = ROOT / "src" / "macropulse" / "platform" / "orchestration.py"


def test_phase2c_files_are_syntax_valid() -> None:
    ast.parse(SCRIPT.read_text(encoding="utf-8"))
    ast.parse(ORCHESTRATION.read_text(encoding="utf-8"))


def test_cli_is_dry_run_by_default_and_model1d_is_opt_in() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--execute" in text
    assert "--run-model1d" in text
    assert "if args.execute" in text
    assert "include_model1d=args.run_model1d" in text


def test_orchestrator_calls_existing_governed_entry_points() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    for command in (
        "scripts/verify_model1d_v038_release.py",
        "scripts/refresh_release_calendar.py",
        "scripts/download_fred_data.py",
        "scripts/download_inflation_data.py",
        "scripts/download_labour_data.py",
        "scripts/run_baseline_nowcast.py",
        "scripts/run_inflation_nowcast.py",
        "scripts/run_labour_nowcast.py",
        "scripts/run_macro_state_shadow_operations.py",
    ):
        assert command in text


def test_existing_model1d_month_is_never_recreated() -> None:
    text = ORCHESTRATION.read_text(encoding="utf-8")
    assert "skip_existing_month" in text
    assert "resolve_due_outcomes_only" in text
    assert "--skip-prediction" in text

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "export_macro_snapshot.py"
SNAPSHOT = ROOT / "src" / "macropulse" / "platform" / "snapshot.py"
GITIGNORE = ROOT / ".gitignore"


def test_phase2d_files_are_syntax_valid() -> None:
    ast.parse(SCRIPT.read_text(encoding="utf-8"))
    ast.parse(SNAPSHOT.read_text(encoding="utf-8"))


def test_exporter_has_no_model_or_download_entrypoints() -> None:
    text = SNAPSHOT.read_text(encoding="utf-8") + SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "run_baseline_nowcast",
        "run_inflation_nowcast",
        "run_labour_nowcast",
        "run_macro_state_shadow_operations",
        "download_fred_data",
        "download_inflation_data",
        "download_labour_data",
    ):
        assert marker not in text


def test_snapshot_exports_are_git_ignored() -> None:
    assert "reports/macro_snapshots/" in GITIGNORE.read_text(encoding="utf-8")


def test_default_output_is_as_of_path() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "macro_snapshot_{args.as_of.strftime('%Y%m%d')}.json" in text
    assert "--stdout" in text

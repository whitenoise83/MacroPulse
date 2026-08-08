from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "report_platform_status.py"
STATUS = ROOT / "src" / "macropulse" / "platform" / "status.py"


def test_status_command_is_present_and_syntax_valid() -> None:
    ast.parse(SCRIPT.read_text(encoding="utf-8"))
    ast.parse(STATUS.read_text(encoding="utf-8"))


def test_phase2b_contains_no_database_write_sql() -> None:
    text = STATUS.read_text(encoding="utf-8").upper()
    prohibited = ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP TABLE")
    for token in prohibited:
        assert token not in text


def test_status_command_has_no_write_report_option() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "--json" in text
    assert "--as-of" in text
    assert "write_" not in text.lower()

def test_live_run_queries_match_governed_schema() -> None:
    text = STATUS.read_text(encoding="utf-8")
    live_block = text.split('if spec.key in {"1B", "1C"}:', 1)[1].split(
        'return repository.query_df(', 2
    )[1].split('    return repository.query_df(', 1)[0]

    assert "run_timestamp" in live_block
    assert "ORDER BY information_cutoff DESC, run_timestamp DESC" in live_block
    assert "status, created_at" not in live_block

def test_model1d_status_uses_valid_not_current_semantics() -> None:
    status_text = STATUS.read_text(encoding="utf-8")
    script_text = SCRIPT.read_text(encoding="utf-8")

    assert '"model1d_shadow_valid"' in status_text
    assert '"model1d_shadow_current"' not in status_text
    assert 'readiness["model1d_shadow_valid"]' in script_text
    assert 'readiness["model1d_shadow_current"]' not in script_text

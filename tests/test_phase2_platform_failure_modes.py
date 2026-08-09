from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from macropulse.platform.orchestration import PlatformOperationError
from macropulse.platform.snapshot import build_macro_snapshot


class NeverRepository:
    def query_df(self, query, parameters=None):
        raise AssertionError("Repository should not be queried.")


def test_future_snapshot_fails_before_repository_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="future"):
        build_macro_snapshot(
            NeverRepository(),
            as_of=date(2999, 1, 1),
            project_root=tmp_path,
        )


def test_platform_operation_error_preserves_failure_context() -> None:
    error = PlatformOperationError("blocked")
    assert str(error) == "blocked"
    assert error.outcomes == []
    assert error.status is None


def test_orchestration_cli_remains_dry_run_by_default() -> None:
    text = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_platform_operations.py"
    ).read_text(encoding="utf-8")
    assert 'parser.add_argument(\n        "--execute"' in text
    assert "if args.execute:" in text


def test_model1d_remains_explicit_opt_in() -> None:
    text = (
        Path(__file__).parents[1]
        / "scripts"
        / "run_platform_operations.py"
    ).read_text(encoding="utf-8")
    assert "--run-model1d" in text
    assert "include_model1d=args.run_model1d" in text


def test_dashboard_has_no_mutating_controls() -> None:
    text = (
        Path(__file__).parents[1]
        / "ui"
        / "platform_dashboard.py"
    ).read_text(encoding="utf-8")
    assert "st.download_button" in text
    assert "st.button(" not in text
    assert "--execute" not in text

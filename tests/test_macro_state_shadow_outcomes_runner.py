from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd


def _load_runner():
    path = Path("scripts") / "resolve_macro_state_shadow_outcomes.py"
    spec = importlib.util.spec_from_file_location(
        "resolve_macro_state_shadow_outcomes_script",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_prints_zero_eligible_summary(monkeypatch, capsys) -> None:
    module = _load_runner()
    monkeypatch.setattr(module, "MacroRepository", lambda: object())
    monkeypatch.setattr(
        module,
        "resolve_macro_state_shadow_outcomes",
        lambda repository, as_of, shadow_run_id: {
            "model_version": "0.3.8",
            "resolution_as_of": date(2026, 8, 5),
            "eligible_runs": 0,
            "resolved_runs": 0,
            "unresolved_runs": 0,
            "outcome_rows_appended": 0,
            "resolved": pd.DataFrame(),
            "unresolved": pd.DataFrame(),
            "promotion_authority": "none",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["resolve_macro_state_shadow_outcomes.py", "--as-of", "2026-08-05"],
    )
    module.main()
    output = capsys.readouterr().out
    assert "outcome resolution complete" in output
    assert "Eligible shadow runs: 0" in output
    assert "Outcome rows appended: 0" in output
    assert "Promotion authority: none" in output


def test_runner_forwards_specific_shadow_run(monkeypatch) -> None:
    module = _load_runner()
    captured = {}
    monkeypatch.setattr(module, "MacroRepository", lambda: object())

    def fake(repository, as_of, shadow_run_id):
        captured["as_of"] = as_of
        captured["shadow_run_id"] = shadow_run_id
        return {
            "model_version": "0.3.8",
            "resolution_as_of": as_of,
            "eligible_runs": 0,
            "resolved_runs": 0,
            "unresolved_runs": 0,
            "outcome_rows_appended": 0,
            "resolved": pd.DataFrame(),
            "unresolved": pd.DataFrame(),
            "promotion_authority": "none",
        }

    monkeypatch.setattr(module, "resolve_macro_state_shadow_outcomes", fake)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "resolve_macro_state_shadow_outcomes.py",
            "--as-of",
            "2026-08-05",
            "--shadow-run-id",
            "shadow-1",
        ],
    )
    module.main()
    assert captured == {
        "as_of": date(2026, 8, 5),
        "shadow_run_id": "shadow-1",
    }

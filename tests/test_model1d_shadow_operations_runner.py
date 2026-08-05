from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


def _load_script(name: str):
    path = Path(__file__).parents[1] / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_monthly_runner_prints_idempotent_status(monkeypatch, capsys) -> None:
    module = _load_script("run_macro_state_shadow_operations.py")
    monkeypatch.setattr(
        module,
        "run_monthly_shadow_operations",
        lambda **kwargs: {
            "model_version": "0.3.8",
            "operation_as_of": date(2026, 8, 5),
            "state_date": date(2026, 8, 31),
            "prediction_action": "skipped_existing_month",
            "shadow_run_id": "run-1",
            "resolved_runs": 0,
            "unresolved_runs": 0,
            "outcome_rows_appended": 0,
            "complete_target_months": 0,
            "minimum_complete_target_months": 12,
            "integrity_pass": True,
            "comparison_permitted": False,
            "promotion_authority": "none",
            "output_paths": {},
        },
    )
    monkeypatch.setattr(sys, "argv", ["runner", "--as-of", "2026-08-05"])
    module.main()
    output = capsys.readouterr().out
    assert "Prediction action: skipped_existing_month" in output
    assert "Complete target months: 0/12" in output
    assert "Promotion authority: none" in output


def test_status_runner_prints_lock(monkeypatch, capsys) -> None:
    module = _load_script("report_macro_state_shadow_status.py")
    import pandas as pd

    monkeypatch.setattr(
        module,
        "run_shadow_monitoring",
        lambda **kwargs: {
            "model_version": "0.3.8",
            "as_of": date(2026, 8, 5),
            "run_status": pd.DataFrame([{"shadow_run_id": "run-1"}]),
            "readiness": pd.DataFrame(
                [
                    {
                        "complete_target_months": 0,
                        "minimum_complete_target_months": 12,
                        "integrity_pass": True,
                        "comparison_permitted": False,
                        "conclusion_status": "insufficient_prospective_evidence",
                        "promotion_authority": "none",
                    }
                ]
            ),
            "integrity_checks": pd.DataFrame(
                [{"check_id": "ok", "passed": True}]
            ),
            "output_paths": {},
        },
    )
    monkeypatch.setattr(sys, "argv", ["status", "--no-write"])
    module.main()
    output = capsys.readouterr().out
    assert "Comparison permitted: no" in output
    assert "insufficient_prospective_evidence" in output

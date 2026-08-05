from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import macropulse.operations.model1d_shadow_operations as operations


class FakeRepository:
    def __init__(self, existing: bool) -> None:
        self.existing = existing
        self.initialised = False

    def initialise(self) -> None:
        self.initialised = True

    def query_df(self, query: str, parameters=None) -> pd.DataFrame:
        if "macro_state_shadow_runs" not in query:
            raise AssertionError(query)
        if not self.existing:
            return pd.DataFrame()
        return pd.DataFrame(
            [
                {
                    "shadow_run_id": "existing-run",
                    "state_date": date(2026, 8, 31),
                    "information_cutoff": date(2026, 8, 5),
                    "status": "predicted",
                }
            ]
        )


def _patch_common(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        operations,
        "load_macro_state_governance",
        lambda root: {"prospective_transition_shadow": {}},
    )
    monkeypatch.setattr(
        operations,
        "prospective_shadow_plan",
        lambda config: SimpleNamespace(model_version="0.3.8"),
    )
    monkeypatch.setattr(
        operations,
        "resolve_macro_state_shadow_outcomes",
        lambda **kwargs: {
            "resolved_runs": 0,
            "unresolved_runs": 0,
            "outcome_rows_appended": 0,
        },
    )
    monkeypatch.setattr(
        operations,
        "run_shadow_monitoring",
        lambda **kwargs: {
            "readiness": pd.DataFrame(
                [
                    {
                        "complete_target_months": 0,
                        "minimum_complete_target_months": 12,
                        "comparison_permitted": False,
                        "promotion_authority": "none",
                        "integrity_pass": True,
                    }
                ]
            ),
            "output_paths": {"report": str(tmp_path / "report.md")},
        },
    )


def test_existing_month_is_skipped(monkeypatch, tmp_path: Path) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setattr(
        operations,
        "run_macro_state_prospective_shadow",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    repository = FakeRepository(existing=True)
    result = operations.run_monthly_shadow_operations(
        repository=repository,
        as_of=date(2026, 8, 5),
        project_root=tmp_path,
    )
    assert repository.initialised
    assert result["prediction_action"] == "skipped_existing_month"
    assert result["shadow_run_id"] == "existing-run"


def test_missing_month_creates_prediction(monkeypatch, tmp_path: Path) -> None:
    _patch_common(monkeypatch, tmp_path)
    monkeypatch.setattr(
        operations,
        "run_macro_state_prospective_shadow",
        lambda **kwargs: {"shadow_run_id": "new-run"},
    )
    repository = FakeRepository(existing=False)
    result = operations.run_monthly_shadow_operations(
        repository=repository,
        as_of=date(2026, 8, 5),
        project_root=tmp_path,
    )
    assert result["prediction_action"] == "created"
    assert result["shadow_run_id"] == "new-run"

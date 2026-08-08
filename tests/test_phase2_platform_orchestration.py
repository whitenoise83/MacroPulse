from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from macropulse.platform.orchestration import (
    PlatformOperationError,
    build_dry_run_plan,
    model1d_gate,
    validate_platform_boundary,
)


class FakeRepository:
    def __init__(self, *, existing_month: bool = True, due_runs: int = 0) -> None:
        self.existing_month = existing_month
        self.due_runs = due_runs

    def query_df(self, query: str, parameters: list | None = None) -> pd.DataFrame:
        compact = " ".join(query.split()).lower()
        if "from macro_state_shadow_runs" in compact and "left join" not in compact:
            if not self.existing_month:
                return pd.DataFrame(
                    columns=["shadow_run_id", "state_date", "information_cutoff", "status"]
                )
            return pd.DataFrame([{
                "shadow_run_id": "shadow-aug",
                "state_date": date(2026, 8, 31),
                "information_cutoff": date(2026, 8, 5),
                "status": "predicted",
            }])
        if "left join macro_state_shadow_outcomes" in compact:
            return pd.DataFrame([
                {
                    "shadow_run_id": f"due-{i}",
                    "state_date": date(2026, 5, 31),
                    "target_expected_available_date": date(2026, 8, 1),
                    "outcome_count": 0,
                }
                for i in range(self.due_runs)
            ])
        raise AssertionError(f"Unexpected query: {compact}")


def write_boundary(root: Path) -> None:
    payload = {
        "phase": "II",
        "model_suite": {
            "1A": {"status": "production", "version": "1.0.0"},
            "1B": {"status": "production", "version": "1.0.0"},
            "1C": {"status": "production", "version": "1.0.0"},
            "1D": {
                "status": "development",
                "version": "0.3.8",
                "mode": "prospective_shadow",
                "promotion_authority": "none",
            },
        },
    }
    (root / "PHASE2_BOUNDARY.json").write_text(json.dumps(payload), encoding="utf-8")


def make_status(
    *,
    ready_1a: bool = True,
    ready_1b: bool = True,
    ready_1c: bool = True,
    cutoff: date = date(2026, 8, 8),
) -> dict:
    rows = []
    for component, ready in [("1A", ready_1a), ("1B", ready_1b), ("1C", ready_1c)]:
        rows.append({
            "component": component,
            "model_id": f"model-{component}",
            "model_version": "1.0.0",
            "lifecycle_status": "production",
            "run_id": f"run-{component}",
            "information_cutoff": cutoff,
            "data_as_of": cutoff,
            "target_period": None,
            "forecast_stage": None,
            "target_count": 1,
            "source_series_count": 1,
            "stale_source_count": 0 if ready else 1,
            "due_release_count": 0 if ready else 1,
            "freshness_state": "fresh" if ready else "stale",
            "ready": ready,
        })
    rows.append({
        "component": "1D",
        "model_id": "US_MACRO_STATE_1D",
        "model_version": "0.3.8",
        "lifecycle_status": "development",
        "run_id": "shadow-aug",
        "information_cutoff": date(2026, 8, 5),
        "data_as_of": date(2026, 8, 31),
        "target_period": "2026-08-31",
        "forecast_stage": "prospective_shadow",
        "target_count": 2,
        "source_series_count": 3,
        "stale_source_count": 0,
        "due_release_count": 0,
        "freshness_state": "frozen_prospective_observation",
        "ready": True,
    })
    all_ready = ready_1a and ready_1b and ready_1c
    return {
        "as_of": cutoff,
        "components": pd.DataFrame(rows),
        "source_health": pd.DataFrame(),
        "due_releases": pd.DataFrame(),
        "upcoming_releases": pd.DataFrame(),
        "model1d": pd.DataFrame(),
        "readiness": pd.DataFrame([{
            "production_sources_ready": all_ready,
            "model1d_shadow_valid": True,
            "platform_ready_for_downstream": all_ready,
            "blocking_components": "" if all_ready else "1B",
            "next_action": "no_model_action_required" if all_ready else "refresh_or_repair_production_source_models",
        }]),
    }


def test_boundary_fails_closed_on_changed_version(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    payload = json.loads((tmp_path / "PHASE2_BOUNDARY.json").read_text())
    payload["model_suite"]["1C"]["version"] = "9.9.9"
    (tmp_path / "PHASE2_BOUNDARY.json").write_text(json.dumps(payload))
    with pytest.raises(PlatformOperationError, match="fails closed"):
        validate_platform_boundary(tmp_path)


def test_dry_run_skips_already_fresh_production_models(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    result = build_dry_run_plan(
        FakeRepository(existing_month=True),
        as_of=date(2026, 8, 8),
        project_root=tmp_path,
        include_model1d=True,
        status_provider=lambda repository, as_of, root: make_status(),
    )
    model_steps = [s for s in result["steps"] if s["step"] == "run_governed_model"]
    assert [s["action"] for s in model_steps] == [
        "skip_already_fresh",
        "skip_already_fresh",
        "skip_already_fresh",
    ]
    assert result["model1d_gate"]["action"] == "skip_existing_month"


def test_model1d_gate_resolution_only(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    gate = model1d_gate(
        FakeRepository(existing_month=True, due_runs=1),
        as_of=date(2026, 8, 8),
        project_root=tmp_path,
        production_status=make_status(),
    )
    assert gate["action"] == "resolve_due_outcomes_only"
    assert gate["eligible"] is True


def test_model1d_gate_new_month_when_absent(tmp_path: Path) -> None:
    write_boundary(tmp_path)
    gate = model1d_gate(
        FakeRepository(existing_month=False, due_runs=0),
        as_of=date(2026, 9, 5),
        project_root=tmp_path,
        production_status=make_status(cutoff=date(2026, 9, 5)),
    )
    assert gate["action"] == "create_monthly_prediction"
    assert gate["eligible"] is True

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import macropulse.macro_state.shadow_outcomes_service as service
from macropulse.macro_state.prospective_shadow import (
    prediction_rows,
    prospective_shadow_plan,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _run() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "shadow_run_id": "shadow-1",
                "model_id": "US_MACRO_STATE_1D",
                "model_version": "0.3.8",
                "run_timestamp": pd.Timestamp("2026-08-05 10:00:00"),
                "state_date": date(2026, 8, 31),
                "information_cutoff": date(2026, 8, 5),
                "target_mode": "fixed_horizon_90d",
                "target_horizon_days": 90,
                "target_expected_available_date": date(2026, 11, 29),
                "source_candidate_id": "candidate",
                "source_evidence_version": "0.3.6",
                "primary_comparator": "rolling_frequency",
                "source_macro_state_run_id": "macro-run-1",
                "gdp_run_id": "gdp-run",
                "inflation_run_id": "inflation-run",
                "labour_run_id": "labour-run",
                "config_hash": "a" * 64,
                "code_hash": "b" * 64,
                "git_commit": "test",
                "information_set_hash": "c" * 64,
                "source_bundle_hash": "d" * 64,
                "no_look_ahead_pass": True,
                "status": "predicted",
                "governance_json": "{}",
                "notes": None,
                "created_at": pd.Timestamp("2026-08-05 10:00:00"),
            }
        ]
    )


def _inputs() -> pd.DataFrame:
    targets = [
        ("GDPC1", "2026Q3", "US_GDP_NOWCAST_1A"),
        ("PCEPILFE", "2026-08", "US_INFLATION_NOWCAST_1B"),
        ("CPILFESL", "2026-08", "US_INFLATION_NOWCAST_1B"),
        ("PCEPI", "2026-08", "US_INFLATION_NOWCAST_1B"),
        ("CPIAUCSL", "2026-08", "US_INFLATION_NOWCAST_1B"),
        ("PAYEMS", "2026-08", "US_LABOUR_NOWCAST_1C"),
        ("UNRATE", "2026-08", "US_LABOUR_NOWCAST_1C"),
        ("CES0500000003", "2026-08", "US_LABOUR_NOWCAST_1C"),
    ]
    return pd.DataFrame(
        [
            {
                "source_target": target,
                "target_period": period,
                "point_forecast": float(index + 1),
                "lower_80": float(index),
                "upper_80": float(index + 2),
                "source_model_id": model,
                "source_model_version": "1.0.0",
                "source_run_id": model + "-run",
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 8, 5),
                "source_hash": target[0].lower() * 64,
            }
            for index, (target, period, model) in enumerate(targets)
        ]
    )


def _predictions() -> pd.DataFrame:
    plan = prospective_shadow_plan(load_macro_state_governance())
    return prediction_rows(
        shadow_run_id="shadow-1",
        model_version="0.3.8",
        state_date=date(2026, 8, 31),
        information_cutoff=date(2026, 8, 5),
        prediction_timestamp=pd.Timestamp("2026-08-05 10:00:00"),
        probability_vectors={
            "source": {
                "adverse_supply": 0.10,
                "benign_expansion": 0.20,
                "contraction": 0.50,
                "inflationary_expansion": 0.10,
                "mixed": 0.10,
            },
            "rolling_frequency": {
                "adverse_supply": 0.10,
                "benign_expansion": 0.40,
                "contraction": 0.20,
                "inflationary_expansion": 0.10,
                "mixed": 0.20,
            },
        },
        plan=plan,
        created_at=pd.Timestamp("2026-08-05 10:00:00"),
    )


def _components() -> pd.DataFrame:
    rows = []
    for index, row in enumerate(_inputs().itertuples(index=False)):
        evaluation = (
            date(2026, 12, 29)
            if row.source_target == "GDPC1"
            else date(2026, 11, 29)
        )
        rows.append(
            {
                "source_target": row.source_target,
                "target_period": row.target_period,
                "requested_evaluation_date": evaluation,
                "release_date": date(2026, 9, 1),
                "snapshot_date": evaluation,
                "snapshot_gap_days": 0,
                "actual_value": float(index + 0.5),
                "availability_status": "available",
            }
        )
    return pd.DataFrame(rows)


class FakeRepository:
    def __init__(self, previous: str | None = "benign_expansion") -> None:
        self.previous = previous
        self.saved: pd.DataFrame | None = None
        self.initialised = False

    def initialise(self) -> None:
        self.initialised = True

    def query_df(self, query: str, parameters=None) -> pd.DataFrame:
        normalised = " ".join(query.split())
        if "SELECT r.* FROM macro_state_shadow_runs r" in normalised:
            return _run()
        if "FROM macro_state_inputs" in normalised:
            return _inputs()
        if "FROM macro_state_shadow_predictions" in normalised:
            return _predictions()
        if (
            "SELECT actual_family FROM macro_state_shadow_outcomes" in normalised
        ):
            return (
                pd.DataFrame([{"actual_family": self.previous}])
                if self.previous is not None
                else pd.DataFrame(columns=["actual_family"])
            )
        raise AssertionError(f"Unexpected query: {normalised}")

    def save_macro_state_shadow_outcomes(self, outcomes: pd.DataFrame) -> None:
        self.saved = outcomes.copy()


def _patch_ready_target(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "_resolve_target_components",
        lambda *args, **kwargs: (_components(), []),
    )
    monkeypatch.setattr(
        service,
        "_actual_target_from_components",
        lambda *args, **kwargs: {
            "actual_dimensions": {
                "growth": -0.25,
                "inflation": -0.50,
                "labour": -0.30,
            },
            "actual_family": "contraction",
            "actual_probabilities": {
                "adverse_supply": 0.05,
                "benign_expansion": 0.10,
                "contraction": 0.70,
                "inflationary_expansion": 0.05,
                "mixed": 0.10,
            },
            "actual_confidence": 0.70,
            "secondary_regime": "demand_slowdown",
            "ambiguity_indicator": False,
        },
    )
    monkeypatch.setattr(service, "_today", lambda: date(2026, 12, 30))
    monkeypatch.setattr(
        service,
        "_utc_now_naive",
        lambda: pd.Timestamp("2026-12-30 12:00:00"),
    )


def test_service_appends_exactly_two_outcomes(monkeypatch) -> None:
    _patch_ready_target(monkeypatch)
    repository = FakeRepository()
    result = service.resolve_macro_state_shadow_outcomes(
        repository=repository,
        as_of=date(2026, 12, 30),
        project_root=Path.cwd(),
    )
    assert repository.initialised is True
    assert result["eligible_runs"] == 1
    assert result["resolved_runs"] == 1
    assert result["outcome_rows_appended"] == 2
    assert repository.saved is not None
    assert set(repository.saved["benchmark_id"]) == {
        "source",
        "rolling_frequency",
    }
    assert repository.saved["transition_flag"].all()
    assert repository.saved["target_available_date"].eq(
        date(2026, 12, 29)
    ).all()
    assert repository.saved["no_look_ahead_pass"].all()


def test_incomplete_target_is_not_persisted(monkeypatch) -> None:
    monkeypatch.setattr(service, "_today", lambda: date(2026, 12, 30))
    monkeypatch.setattr(
        service,
        "_utc_now_naive",
        lambda: pd.Timestamp("2026-12-30 12:00:00"),
    )
    monkeypatch.setattr(
        service,
        "_resolve_target_components",
        lambda *args, **kwargs: (
            _components().iloc[:-1].copy(),
            [
                {
                    "source_target": "UNRATE",
                    "availability_status": "missing_snapshot",
                    "detail": "not cached",
                }
            ],
        ),
    )
    repository = FakeRepository()
    result = service.resolve_macro_state_shadow_outcomes(
        repository=repository,
        as_of=date(2026, 12, 30),
        project_root=Path.cwd(),
    )
    assert result["resolved_runs"] == 0
    assert result["unresolved_runs"] == 1
    assert result["outcome_rows_appended"] == 0
    assert repository.saved is None


def test_future_resolution_cutoff_is_prohibited(monkeypatch) -> None:
    monkeypatch.setattr(service, "_today", lambda: date(2026, 8, 5))
    with pytest.raises(ValueError, match="cannot be later"):
        service.resolve_macro_state_shadow_outcomes(
            repository=FakeRepository(),
            as_of=date(2026, 8, 6),
            project_root=Path.cwd(),
        )


def test_strict_component_availability_uses_gdp_quarter_end() -> None:
    assert service._component_evaluation_date(
        "GDPC1", "2026Q3", 90
    ) == date(2026, 12, 29)
    assert service._component_evaluation_date(
        "CPIAUCSL", "2026-08", 90
    ) == date(2026, 11, 29)

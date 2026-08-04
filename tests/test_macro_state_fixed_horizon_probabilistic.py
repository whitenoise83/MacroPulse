from __future__ import annotations

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from macropulse.macro_state.fixed_horizon_probabilistic import (
    BENCHMARKS,
    brier_decomposition,
    build_benchmark_predictions,
    calibration_error,
    dirichlet_smooth,
    fixed_horizon_missing_evidence,
    fixed_horizon_plan,
    fixed_horizon_state_availability,
    locked_target_frame,
)
from macropulse.macro_state.realtime_soft_targets import FAMILIES
from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.tournament import ALL_TARGETS
from macropulse.macro_state.versioning import load_macro_state_governance


def _soft_target_rows(months: int = 18) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = tuple(pd.date_range("2020-01-31", periods=months, freq="ME").date)
    target_rows: list[dict] = []
    vintage_rows: list[dict] = []
    family_order = list(FAMILIES)
    for index, state_date in enumerate(dates):
        actual_family = family_order[index % len(family_order)]
        actual_probabilities = {
            family: (0.70 if family == actual_family else 0.30 / (len(FAMILIES) - 1))
            for family in FAMILIES
        }
        source_probabilities = {
            family: (0.65 if family == actual_family else 0.35 / (len(FAMILIES) - 1))
            for family in FAMILIES
        }
        target_rows.append(
            {
                "target_mode": "fixed_horizon_90d",
                "state_date": state_date,
                "primary_family": actual_family,
                "secondary_regime": "mixed_transition",
                "family_top_probability": 0.70,
                "family_probabilities_json": json.dumps(actual_probabilities),
                "forecast_family_probabilities_json": json.dumps(source_probabilities),
            }
        )
        for target in ALL_TARGETS:
            vintage_rows.append(
                {
                    "state_date": state_date,
                    "source_target": target,
                    "target_period": str(pd.Period(state_date, freq="M")),
                    "target_mode": "fixed_horizon_90d",
                    "actual_value": float(index),
                    "requested_evaluation_date": state_date + timedelta(days=90),
                    "actual_as_of_date": state_date + timedelta(days=85),
                    "availability_status": "available",
                    "snapshot_gap_days": 5,
                }
            )
    return pd.DataFrame(target_rows), pd.DataFrame(vintage_rows)


def _plan(dates: tuple[date, ...]) -> RollingTournamentPlan:
    return RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:12], dates[12:15]),
            RollingFold("fold_02", dates[:15], dates[15:18]),
        ),
        selection_dates=dates,
        audit_dates=tuple(),
    )


def test_fixed_horizon_plan_is_prespecified() -> None:
    config = load_macro_state_governance()
    plan = fixed_horizon_plan(config)
    assert plan.primary_target_mode == "fixed_horizon_90d"
    assert plan.governance_reference == "soft_persistence"
    assert plan.calibration_bins == 5
    assert plan.prospective_shadow_start == date(2026, 4, 30)


def test_dirichlet_smoothing_is_positive_and_normalised() -> None:
    values = {family: 1.0 if index == 0 else 0.0 for index, family in enumerate(FAMILIES)}
    smoothed = dirichlet_smooth(values, 0.1)
    assert abs(sum(smoothed.values()) - 1.0) < 1e-12
    assert all(value > 0 for value in smoothed.values())


def test_missing_evidence_is_explicit() -> None:
    _, vintages = _soft_target_rows(4)
    mask = (
        (vintages["state_date"] == sorted(vintages["state_date"].unique())[-1])
        & (vintages["source_target"] == ALL_TARGETS[0])
    )
    vintages.loc[mask, "actual_value"] = np.nan
    vintages.loc[mask, "availability_status"] = "missing_snapshot"
    availability = fixed_horizon_state_availability(vintages)
    missing = fixed_horizon_missing_evidence(vintages)
    assert int((~availability["complete_state"]).sum()) == 1
    assert len(missing) == 1
    assert missing.iloc[0]["availability_status"] == "missing_snapshot"


def test_benchmarks_use_only_available_target_history() -> None:
    config = load_macro_state_governance()
    targets, vintages = _soft_target_rows()
    availability = fixed_horizon_state_availability(vintages)
    locked = locked_target_frame(targets, availability)
    dates = tuple(targets["state_date"])
    predictions = build_benchmark_predictions(locked, _plan(dates), config)
    assert set(predictions["benchmark_id"]) == set(BENCHMARKS)
    assert predictions["availability_no_lookahead"].all()
    assert (
        pd.to_datetime(predictions["latest_target_available_date"])
        <= pd.to_datetime(predictions["state_date"])
    ).all()


def test_calibration_and_brier_decomposition_are_finite() -> None:
    config = load_macro_state_governance()
    targets, vintages = _soft_target_rows()
    availability = fixed_horizon_state_availability(vintages)
    locked = locked_target_frame(targets, availability)
    dates = tuple(targets["state_date"])
    frame = build_benchmark_predictions(locked, _plan(dates), config)
    source = frame.loc[frame["benchmark_id"] == "source"]
    assert np.isfinite(calibration_error(source, 5))
    decomposition = brier_decomposition(source, 5)
    assert all(np.isfinite(value) for value in decomposition.values())
    assert decomposition["hard_brier"] >= 0


def test_model_identity_is_v036() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.6"

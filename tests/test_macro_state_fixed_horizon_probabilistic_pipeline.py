from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd

from macropulse.macro_state.fixed_horizon_probabilistic import (
    BENCHMARKS,
    run_fixed_horizon_probabilistic_audit,
)
from macropulse.macro_state.realtime_soft_targets import FAMILIES
from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.tournament import ALL_TARGETS
from macropulse.macro_state.versioning import load_macro_state_governance


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, RollingTournamentPlan]:
    dates = tuple(pd.date_range("2020-01-31", periods=24, freq="ME").date)
    soft_rows: list[dict] = []
    vintage_rows: list[dict] = []
    for index, state_date in enumerate(dates):
        actual_family = FAMILIES[index % len(FAMILIES)]
        actual = {
            family: (0.75 if family == actual_family else 0.25 / (len(FAMILIES) - 1))
            for family in FAMILIES
        }
        source = {
            family: (0.68 if family == actual_family else 0.32 / (len(FAMILIES) - 1))
            for family in FAMILIES
        }
        soft_rows.append(
            {
                "target_mode": "fixed_horizon_90d",
                "state_date": state_date,
                "primary_family": actual_family,
                "secondary_regime": "mixed_transition",
                "family_top_probability": 0.75,
                "family_probabilities_json": json.dumps(actual),
                "forecast_family_probabilities_json": json.dumps(source),
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
                    "actual_as_of_date": state_date + timedelta(days=88),
                    "availability_status": "available",
                    "snapshot_gap_days": 2,
                }
            )
    plan = RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:12], dates[12:18]),
            RollingFold("fold_02", dates[:15], dates[15:21]),
        ),
        selection_dates=dates[:21],
        audit_dates=dates[21:],
    )
    source_monthly = pd.DataFrame({"state_date": dates})
    return pd.DataFrame(vintage_rows), pd.DataFrame(soft_rows), source_monthly, plan


def test_fixed_horizon_pipeline_produces_complete_evidence() -> None:
    config = load_macro_state_governance()
    actual_vintages, soft_targets, source_monthly, plan = _inputs()
    result = run_fixed_horizon_probabilistic_audit(
        actual_vintages=actual_vintages,
        soft_targets=soft_targets,
        source_monthly=source_monthly,
        plan=plan,
        config=config,
    )
    assert result["target_lock"].iloc[0]["primary_target_mode"] == "fixed_horizon_90d"
    assert set(result["benchmark_summary"]["benchmark_id"]) == set(BENCHMARKS)
    assert result["benchmark_fold_metrics"]["fold_id"].nunique() == 2
    assert len(result["governance_flags"]) == 12
    assert not result["reliability"].empty
    assert result["prospective_shadow"].iloc[0]["prospective_isolation_pass"]

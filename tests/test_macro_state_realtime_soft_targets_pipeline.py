from __future__ import annotations

import json
from datetime import timedelta

import numpy as np
import pandas as pd

from macropulse.macro_state.realtime_soft_targets import run_realtime_soft_target_audit
from macropulse.macro_state.rolling_tournament import RollingFold, RollingTournamentPlan
from macropulse.macro_state.tournament import (
    ALL_TARGETS,
    GDP_TARGET,
    build_core_candidates,
    candidate_monthly_states,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    config = load_macro_state_governance()
    core = {
        item["candidate_id"]: item for item in build_core_candidates(config)
    }["expanding_robust_z__policy__equal__sensitive"]
    centered = config["tournament"]["normalization_candidates"]["target_centered"]
    dates = tuple(pd.date_range("2020-01-31", periods=36, freq="ME").date)
    rows: list[dict] = []
    for index, state_date in enumerate(dates):
        signal = float(np.sin(index / 4.0))
        for target in ALL_TARGETS:
            center = float(centered["centers"][target])
            scale = float(centered["scales"][target])
            orientation = float(centered["orientation"][target])
            actual = center + orientation * scale * signal
            point = actual + orientation * scale * 0.12
            period = (
                str(pd.Period(state_date, freq="Q"))
                if target == GDP_TARGET
                else str(pd.Period(state_date, freq="M"))
            )
            rows.append(
                {
                    "state_date": state_date,
                    "source_target": target,
                    "target_period": period,
                    "target_period_ordinal": int(
                        pd.Period(period, freq="Q" if target == GDP_TARGET else "M").ordinal
                    ),
                    "point_forecast": point,
                    "lower_80": point - abs(scale) * 0.25,
                    "upper_80": point + abs(scale) * 0.25,
                    "actual": actual,
                    "actual_release_date": state_date + timedelta(days=30),
                }
            )
    dataset = pd.DataFrame(rows)
    source_monthly = candidate_monthly_states(dataset, core, config)
    source_monthly["probabilities_json"] = source_monthly["forecast_regime"].map(
        lambda regime: json.dumps(
            {label: 1.0 if label == regime else 0.0 for label in (
                "hard_landing_risk",
                "stagflation_risk",
                "overheating",
                "disinflationary_expansion",
                "balanced_expansion",
                "reflation",
                "demand_slowdown",
                "mixed_transition",
            )},
            sort_keys=True,
        )
    )
    vintage_rows: list[dict] = []
    for row in dataset.itertuples(index=False):
        for mode, adjustment in (
            ("initial_release", 0.0),
            ("fixed_horizon_90d", 0.01),
            ("latest_revised", 0.02),
        ):
            vintage_rows.append(
                {
                    "state_date": row.state_date,
                    "source_target": row.source_target,
                    "target_period": row.target_period,
                    "target_mode": mode,
                    "actual_value": float(row.actual) + adjustment,
                    "availability_status": "available",
                }
            )
    actual_vintages = pd.DataFrame(vintage_rows)
    return dataset, actual_vintages, source_monthly, core


def test_realtime_soft_target_pipeline_produces_complete_evidence() -> None:
    config = load_macro_state_governance()
    dataset, actual_vintages, source_monthly, core = _synthetic_inputs()
    dates = tuple(source_monthly["state_date"])
    plan = RollingTournamentPlan(
        folds=(
            RollingFold("fold_01", dates[:18], dates[18:24]),
            RollingFold("fold_02", dates[:21], dates[21:27]),
        ),
        selection_dates=dates[:27],
        audit_dates=dates[27:],
    )
    result = run_realtime_soft_target_audit(
        dataset=dataset,
        actual_vintages=actual_vintages,
        source_monthly=source_monthly,
        core_candidate=core,
        plan=plan,
        config=config,
    )
    assert set(result["mode_completeness"]["target_mode"]) == {
        "initial_release",
        "fixed_horizon_90d",
        "latest_revised",
    }
    assert len(result["benchmark_summary"]) == 6
    assert len(result["vintage_agreement"]) == 3
    assert len(result["governance_flags"]) == 9
    assert not result["soft_targets"].empty
    assert result["prospective_shadow"].iloc[0]["prospective_isolation_pass"]

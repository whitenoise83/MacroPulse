from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from macropulse.macro_state.tournament import (
    run_core_tournament,
    run_uncertainty_tournament,
)
from pathlib import Path
import yaml


def load_macro_state_governance() -> dict:
    root = Path(__file__).resolve().parents[1]
    return yaml.safe_load(
        (root / "config" / "macro_state_governance.yml").read_text(
            encoding="utf-8"
        )
    )


TARGETS = {
    "GDPC1": (2.0, 1.0, "Q"),
    "PCEPILFE": (2.0, 0.6, "M"),
    "CPILFESL": (2.3, 0.7, "M"),
    "PCEPI": (2.0, 0.8, "M"),
    "CPIAUCSL": (2.3, 0.9, "M"),
    "PAYEMS": (100.0, 45.0, "M"),
    "UNRATE": (4.5, 0.4, "M"),
    "CES0500000003": (3.3, 0.5, "M"),
}


def _synthetic_dataset() -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2020-01-31", periods=73, freq="ME")
    for index, state_date in enumerate(dates):
        cycle = np.sin(index / 5.0)
        for target, (center, scale, frequency) in TARGETS.items():
            orientation = -1.0 if target == "UNRATE" else 1.0
            actual = center + orientation * scale * cycle
            point = actual + orientation * scale * 0.15 * np.cos(index / 3.0)
            period = pd.Period(state_date, freq=frequency)
            rows.append(
                {
                    "state_date": state_date.date(),
                    "source_target": target,
                    "target_period": str(period),
                    "target_period_ordinal": int(period.ordinal),
                    "point_forecast": point,
                    "lower_80": point - abs(scale),
                    "upper_80": point + abs(scale),
                    "actual": actual,
                }
            )
    return pd.DataFrame(rows)


def test_full_tournament_pipeline_runs_on_synthetic_history() -> None:
    config = copy.deepcopy(load_macro_state_governance())
    config["tournament"]["top_core_candidates"] = 2
    config["tournament"]["uncertainty_draws"] = 64
    dataset = _synthetic_dataset()
    (
        split,
        candidates,
        monthly,
        core_metrics,
        core_leaderboard,
        baselines,
    ) = run_core_tournament(dataset, config)
    assert len(candidates) == 81
    assert len(monthly) == 81
    assert len(core_metrics) == 162
    assert len(core_leaderboard) == 81
    assert len(split.holdout_dates) == 19
    assert "validation_mode_accuracy" in baselines

    final_leaderboard, uncertainty_metrics, monthly_final = (
        run_uncertainty_tournament(
            core_candidates=candidates,
            monthly_by_candidate=monthly,
            core_leaderboard=core_leaderboard,
            split=split,
            config=config,
        )
    )
    assert len(final_leaderboard) == 6
    assert len(uncertainty_metrics) == 12
    assert len(monthly_final) == 6
    assert int(final_leaderboard["final_rank"].min()) == 1
    assert int(final_leaderboard["holdout_final_rank"].min()) == 1

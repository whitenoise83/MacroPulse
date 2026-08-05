from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from macropulse.macro_state.prospective_shadow import (
    prediction_rows,
    prospective_shadow_plan,
)
from macropulse.macro_state.shadow_outcomes import (
    build_outcome_rows,
    score_prediction,
    target_hash,
    transition_flag,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _plan():
    return prospective_shadow_plan(load_macro_state_governance())


def _predictions() -> pd.DataFrame:
    plan = _plan()
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


def _actual() -> dict[str, float]:
    return {
        "adverse_supply": 0.05,
        "benign_expansion": 0.10,
        "contraction": 0.70,
        "inflationary_expansion": 0.05,
        "mixed": 0.10,
    }


def _components() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "source_target": target,
                "target_period": "2026-08",
                "requested_evaluation_date": date(2026, 11, 29),
                "snapshot_date": date(2026, 11, 28),
                "snapshot_gap_days": 1,
                "actual_value": float(index),
            }
            for index, target in enumerate(
                [
                    "GDPC1",
                    "PCEPILFE",
                    "CPILFESL",
                    "PCEPI",
                    "CPIAUCSL",
                    "PAYEMS",
                    "UNRATE",
                    "CES0500000003",
                ]
            )
        ]
    )


def test_soft_target_scoring_is_deterministic() -> None:
    plan = _plan()
    prediction = _predictions().loc[
        lambda frame: frame["benchmark_id"] == "source"
    ].iloc[0].to_dict()
    result = score_prediction(
        prediction=prediction,
        actual_family="contraction",
        actual_probabilities=_actual(),
        target_hash_value="t" * 64,
        log_loss_floor=1.0e-12,
        plan=plan,
    )
    assert result["actual_probability"] == pytest.approx(0.50)
    assert result["brier_score"] == pytest.approx(0.055)
    assert result["log_loss"] > 0
    assert result["top1_hit"] is True
    assert result["top2_hit"] is True
    assert result["top3_hit"] is True
    assert len(result["evaluation_hash"]) == 64


def test_outcome_rows_preserve_two_benchmarks_and_transition() -> None:
    plan = _plan()
    run = {
        "shadow_run_id": "shadow-1",
        "model_version": "0.3.8",
        "state_date": date(2026, 8, 31),
        "target_mode": "fixed_horizon_90d",
        "target_horizon_days": 90,
    }
    rows = build_outcome_rows(
        shadow_run=run,
        predictions=_predictions(),
        resolved_at=pd.Timestamp("2026-12-30 12:00:00"),
        target_available_date=date(2026, 12, 29),
        target_vintage_id="fixed-horizon-test",
        actual_family="contraction",
        actual_probabilities=_actual(),
        actual_confidence=0.70,
        previous_actual_family="benign_expansion",
        target_hash_value="t" * 64,
        log_loss_floor=1.0e-12,
        plan=plan,
    )
    assert len(rows) == 2
    assert set(rows["benchmark_id"]) == {"source", "rolling_frequency"}
    assert rows["transition_flag"].all()
    assert rows["previous_actual_family"].eq("benign_expansion").all()
    assert rows["target_hash"].eq("t" * 64).all()
    assert rows["evaluation_hash"].nunique() == 2


def test_prediction_tampering_is_rejected() -> None:
    plan = _plan()
    prediction = _predictions().iloc[0].to_dict()
    prediction["top1_family"] = "mixed"
    with pytest.raises(ValueError, match="does not reconcile"):
        score_prediction(
            prediction=prediction,
            actual_family="contraction",
            actual_probabilities=_actual(),
            target_hash_value="t" * 64,
            log_loss_floor=1.0e-12,
            plan=plan,
        )


def test_target_hash_is_order_invariant_and_transition_first_month_is_false() -> None:
    plan = _plan()
    kwargs = {
        "state_date": date(2026, 8, 31),
        "target_mode": "fixed_horizon_90d",
        "target_horizon_days": 90,
        "target_available_date": date(2026, 12, 29),
        "actual_dimensions": {
            "growth": -0.2,
            "inflation": -0.5,
            "labour": -0.3,
        },
        "actual_family": "contraction",
        "actual_probabilities": _actual(),
        "actual_confidence": 0.70,
        "plan": plan,
    }
    first = target_hash(target_components=_components(), **kwargs)
    second = target_hash(
        target_components=_components().sample(frac=1.0, random_state=4),
        **kwargs,
    )
    assert first == second
    assert len(first) == 64
    assert transition_flag("contraction", None) is False

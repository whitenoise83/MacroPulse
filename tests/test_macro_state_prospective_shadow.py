from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from macropulse.macro_state.prospective_shadow import (
    build_source_dimensions,
    probability_diagnostics,
    prospective_shadow_plan,
    rolling_frequency_probabilities,
    source_family_probabilities,
    validate_probability_vector,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _plan():
    return prospective_shadow_plan(load_macro_state_governance())


def _current_inputs() -> pd.DataFrame:
    specs = [
        ("GDPC1", "US_GDP_NOWCAST_1A", "gdp-run", 2.8, 1.8, 3.8),
        ("PCEPILFE", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.0, 2.4, 3.6),
        ("CPILFESL", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.2, 2.6, 3.8),
        ("PCEPI", "US_INFLATION_NOWCAST_1B", "inflation-run", 2.8, 2.2, 3.4),
        ("CPIAUCSL", "US_INFLATION_NOWCAST_1B", "inflation-run", 3.1, 2.5, 3.7),
        ("PAYEMS", "US_LABOUR_NOWCAST_1C", "labour-run", 150.0, 90.0, 210.0),
        ("UNRATE", "US_LABOUR_NOWCAST_1C", "labour-run", 4.2, 3.9, 4.5),
        ("CES0500000003", "US_LABOUR_NOWCAST_1C", "labour-run", 3.8, 3.2, 4.4),
    ]
    return pd.DataFrame(
        [
            {
                "source_target": target,
                "source_model_id": model_id,
                "source_model_version": "1.0.0",
                "source_run_id": run_id,
                "point_forecast": point,
                "lower_80": lower,
                "upper_80": upper,
                "information_cutoff": date(2026, 8, 5),
                "data_as_of": date(2026, 8, 5),
                "source_hash": target.lower() * 8,
            }
            for target, model_id, run_id, point, lower, upper in specs
        ]
    )


def _history() -> pd.DataFrame:
    rows = []
    targets = _current_inputs()["source_target"].tolist()
    for index, state_date in enumerate(
        pd.date_range("2024-01-31", periods=24, freq="ME")
    ):
        for target_index, target in enumerate(targets):
            base = float(_current_inputs().set_index("source_target").loc[target, "point_forecast"])
            rows.append(
                {
                    "state_date": state_date.date(),
                    "source_target": target,
                    "point_forecast": base + 0.05 * np.sin(index + target_index),
                }
            )
    return pd.DataFrame(rows)


def test_probability_contract_and_tie_break_are_deterministic() -> None:
    plan = _plan()
    values = {family: 0.2 for family in plan.family_order}
    validated = validate_probability_vector(values, plan)
    diagnostics = probability_diagnostics(validated, plan)
    assert diagnostics["top1_family"] == plan.family_order[0]
    assert diagnostics["top2_family"] == plan.family_order[1]
    assert diagnostics["probability_sum"] == pytest.approx(1.0)
    assert len(diagnostics["probability_vector_hash"]) == 64


def test_probability_contract_rejects_wrong_family_set() -> None:
    plan = _plan()
    with pytest.raises(ValueError, match="families"):
        validate_probability_vector({"mixed": 1.0}, plan)


def test_source_dimensions_are_candidate_specific_and_complete() -> None:
    config = load_macro_state_governance()
    plan = prospective_shadow_plan(config)
    dimensions = build_source_dimensions(
        history_inputs=_history(),
        current_inputs=_current_inputs(),
        config=config,
        plan=plan,
    )
    assert set(dimensions["dimension"]) == {"growth", "inflation", "labour"}
    assert dimensions[["score", "lower_score", "upper_score"]].notna().all().all()
    assert (dimensions["lower_score"] <= dimensions["score"]).all()
    assert (dimensions["score"] <= dimensions["upper_score"]).all()
    assert dimensions["details_json"].str.contains("expanding_robust_z").all()


def test_independent_normal_source_probabilities_are_reproducible() -> None:
    config = load_macro_state_governance()
    plan = prospective_shadow_plan(config)
    dimensions = build_source_dimensions(
        history_inputs=_history(),
        current_inputs=_current_inputs(),
        config=config,
        plan=plan,
    )
    first = source_family_probabilities(
        dimensions,
        state_date=date(2026, 8, 31),
        config=config,
        plan=plan,
    )
    second = source_family_probabilities(
        dimensions,
        state_date=date(2026, 8, 31),
        config=config,
        plan=plan,
    )
    assert first == second
    assert set(first) == set(plan.family_order)
    assert sum(first.values()) == pytest.approx(1.0)


def test_rolling_frequency_uses_only_available_prior_states() -> None:
    plan = _plan()
    history = pd.DataFrame(
        [
            {
                "state_date": date(2026, month, 28),
                "primary_family": family,
                "state_available_date": available,
            }
            for month, family, available in [
                (1, "mixed", date(2026, 4, 28)),
                (2, "benign_expansion", date(2026, 5, 29)),
                (3, "inflationary_expansion", date(2026, 6, 29)),
                (4, "contraction", date(2026, 12, 1)),
            ]
        ]
    )
    probabilities, used = rolling_frequency_probabilities(
        history,
        information_cutoff=date(2026, 8, 5),
        state_date=date(2026, 8, 31),
        plan=plan,
    )
    assert len(used) == 3
    assert probabilities["contraction"] == 0.0
    assert probabilities["mixed"] == pytest.approx(1.0 / 3.0)

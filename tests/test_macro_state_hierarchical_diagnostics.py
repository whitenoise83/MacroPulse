from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from macropulse.macro_state.hierarchical_diagnostics import (
    apply_dimension_calibration,
    build_hierarchical_candidates,
    classify_hierarchical_regime,
    fit_dimension_calibration,
)
from macropulse.macro_state.versioning import load_macro_state_governance


def _training() -> pd.DataFrame:
    values = np.linspace(-1.5, 1.5, 24)
    return pd.DataFrame(
        {
            "forecast_growth": values + 0.5,
            "actual_growth": values,
            "forecast_inflation": values - 0.2,
            "actual_inflation": values,
            "forecast_labour": values - 0.3,
            "actual_labour": values,
        }
    )


def test_candidate_grid_is_small_and_prespecified() -> None:
    config = load_macro_state_governance()
    candidates = build_hierarchical_candidates(config)
    assert len(candidates) == 9
    assert len({item["candidate_id"] for item in candidates}) == 9


def test_expanding_bias_correction_removes_training_bias() -> None:
    config = load_macro_state_governance()
    calibrations = fit_dimension_calibration(
        _training(), "expanding_bias", config
    )
    assert abs(calibrations["growth"].alpha + 0.5) < 1e-12
    assert abs(calibrations["inflation"].alpha - 0.2) < 1e-12
    assert abs(calibrations["labour"].alpha - 0.3) < 1e-12
    assert max(
        abs(item.post_bias) for item in calibrations.values()
    ) < 1e-12


def test_affine_shrinkage_is_bounded_and_causal() -> None:
    config = load_macro_state_governance()
    training = _training()
    training["actual_growth"] = 0.2 + 1.4 * training["forecast_growth"]
    calibrations = fit_dimension_calibration(
        training, "expanding_affine_shrinkage", config
    )
    growth = calibrations["growth"]
    assert 1.0 < growth.beta <= 1.75
    assert abs(growth.alpha) <= 1.0
    assert abs(growth.post_bias) < abs(growth.pre_bias)


def test_apply_calibration_preserves_interval_order() -> None:
    config = load_macro_state_governance()
    calibrations = fit_dimension_calibration(
        _training(), "expanding_bias", config
    )
    frame = pd.DataFrame(
        {
            "forecast_growth": [0.5],
            "growth_lower": [-1.0],
            "growth_upper": [1.0],
            "forecast_inflation": [0.2],
            "inflation_lower": [-0.5],
            "inflation_upper": [0.8],
            "forecast_labour": [-0.3],
            "labour_lower": [-1.2],
            "labour_upper": [0.6],
        }
    )
    output = apply_dimension_calibration(frame, calibrations)
    for dimension in ("growth", "inflation", "labour"):
        assert output.iloc[0][f"{dimension}_lower"] <= output.iloc[0][
            f"{dimension}_upper"
        ]


def test_family_first_classifies_stagflation() -> None:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    regime, family, abstained, count = classify_hierarchical_regime(
        growth=-1.0,
        inflation=1.2,
        labour=-0.4,
        growth_lower=-1.2,
        growth_upper=-0.8,
        inflation_lower=1.0,
        inflation_upper=1.4,
        labour_lower=-0.8,
        labour_upper=0.0,
        architecture_id="family_first",
        thresholds=thresholds,
        config=config,
    )
    assert regime == "stagflation_risk"
    assert family == "adverse_supply"
    assert abstained is False
    assert count == 1


def test_interval_architecture_abstains_when_families_disagree() -> None:
    config = load_macro_state_governance()
    thresholds = config["tournament"]["threshold_candidates"]["sensitive"]
    regime, family, abstained, count = classify_hierarchical_regime(
        growth=0.4,
        inflation=0.4,
        labour=0.2,
        growth_lower=-0.8,
        growth_upper=1.2,
        inflation_lower=-0.8,
        inflation_upper=1.2,
        labour_lower=-1.0,
        labour_upper=1.0,
        architecture_id="family_first_interval_abstain",
        thresholds=thresholds,
        config=config,
    )
    assert regime == "mixed_transition"
    assert family == "mixed"
    assert abstained is True
    assert count > 1


def test_model_identity_is_v034() -> None:
    config = load_macro_state_governance()
    assert config["model"]["version"] == "0.3.4"

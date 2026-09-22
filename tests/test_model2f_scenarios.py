from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.model import (
    VARIABLES,
    candidate_grid,
    fit_bvar,
    point_forecast,
)
from macropulse.bvar.scenario import (
    BASELINE_LABEL,
    SCENARIO_LABEL,
    SCENARIO_PATH_HORIZONS,
    SCENARIO_REPORT_HORIZONS,
    run_path_scenario,
    unconditional_baseline_path,
)


def synthetic_panel(periods: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(12345)
    values = np.zeros((periods, 4), dtype=float)
    values[0] = [2.0, 2.2, 4.5, 3.0]

    transition = np.array(
        [
            [0.30, 0.04, -0.02, -0.01],
            [0.05, 0.40, -0.02, 0.03],
            [-0.03, 0.02, 0.82, 0.02],
            [0.04, 0.08, -0.03, 0.72],
        ],
        dtype=float,
    )
    intercept = np.array([1.2, 1.1, 0.75, 0.8])
    noise_scale = np.array([0.30, 0.25, 0.06, 0.08])

    for t in range(1, periods):
        values[t] = (
            intercept
            + transition @ values[t - 1]
            + rng.normal(scale=noise_scale, size=4)
        )

    return pd.DataFrame(
        values,
        index=pd.period_range("2000Q1", periods=periods, freq="Q"),
        columns=list(VARIABLES),
    )


def fitted():
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    return panel, posterior


def policy_constraint(
    panel: pd.DataFrame,
    posterior,
    *,
    horizon: int = 1,
    increment: float = 1.0,
) -> pd.DataFrame:
    baseline = unconditional_baseline_path(panel, posterior)
    row = baseline.loc[baseline["horizon"] == horizon].iloc[0]
    return pd.DataFrame(
        [
            {
                "horizon": horizon,
                "variable": "policy_rate",
                "value": float(row["policy_rate"]) + increment,
            }
        ]
    )


def test_scenario_constants_are_frozen() -> None:
    assert SCENARIO_PATH_HORIZONS == tuple(range(1, 9))
    assert SCENARIO_REPORT_HORIZONS == (1, 2, 4, 8)
    assert SCENARIO_LABEL == "scenario"
    assert BASELINE_LABEL == "unconditional_baseline"


def test_unconditional_baseline_matches_model2c_point_forecast() -> None:
    panel, posterior = fitted()
    baseline = unconditional_baseline_path(panel, posterior)
    point = point_forecast(panel, posterior)

    for row in point.itertuples(index=False):
        baseline_row = baseline.loc[
            baseline["horizon"] == row.horizon
        ].iloc[0]
        for variable in VARIABLES:
            assert float(baseline_row[variable]) == pytest.approx(
                float(getattr(row, variable)),
                rel=0.0,
                abs=1e-12,
            )


def test_constraint_is_imposed_exactly() -> None:
    panel, posterior = fitted()
    constraints = policy_constraint(
        panel,
        posterior,
        horizon=2,
        increment=1.25,
    )
    result = run_path_scenario(
        panel,
        posterior,
        constraints,
        scenario_name="higher policy path",
    )
    expected = float(constraints.iloc[0]["value"])
    actual = float(
        result.scenario_path.loc[
            result.scenario_path["horizon"] == 2,
            "policy_rate",
        ].iloc[0]
    )
    assert actual == expected


def test_constraint_propagates_to_later_path() -> None:
    panel, posterior = fitted()
    constraints = policy_constraint(
        panel,
        posterior,
        horizon=1,
        increment=2.0,
    )
    result = run_path_scenario(
        panel,
        posterior,
        constraints,
        scenario_name="higher policy path",
    )

    baseline_h4 = result.baseline_path.loc[
        result.baseline_path["horizon"] == 4,
        list(VARIABLES),
    ].to_numpy(dtype=float)
    scenario_h4 = result.scenario_path.loc[
        result.scenario_path["horizon"] == 4,
        list(VARIABLES),
    ].to_numpy(dtype=float)

    assert not np.array_equal(baseline_h4, scenario_h4)


def test_deviations_are_zero_before_first_constraint() -> None:
    panel, posterior = fitted()
    constraints = policy_constraint(
        panel,
        posterior,
        horizon=4,
        increment=1.0,
    )
    result = run_path_scenario(
        panel,
        posterior,
        constraints,
        scenario_name="later policy path",
    )

    early = result.comparison[
        result.comparison["horizon"].isin([1, 2])
    ]
    np.testing.assert_allclose(
        early["deviation"].to_numpy(dtype=float),
        0.0,
        rtol=0.0,
        atol=1e-12,
    )


def test_scenario_id_is_deterministic() -> None:
    panel, posterior = fitted()
    constraints = policy_constraint(panel, posterior)

    first = run_path_scenario(
        panel,
        posterior,
        constraints,
        scenario_name="policy scenario",
    )
    second = run_path_scenario(
        panel,
        posterior,
        constraints.copy(),
        scenario_name="policy scenario",
    )
    assert first.scenario_id == second.scenario_id


def test_different_constraints_change_scenario_id() -> None:
    panel, posterior = fitted()
    first = run_path_scenario(
        panel,
        posterior,
        policy_constraint(panel, posterior, increment=1.0),
        scenario_name="policy scenario",
    )
    second = run_path_scenario(
        panel,
        posterior,
        policy_constraint(panel, posterior, increment=2.0),
        scenario_name="policy scenario",
    )
    assert first.scenario_id != second.scenario_id


def test_duplicate_constraint_fails_closed() -> None:
    panel, posterior = fitted()
    constraints = pd.DataFrame(
        [
            {"horizon": 1, "variable": "policy_rate", "value": 4.0},
            {"horizon": 1, "variable": "policy_rate", "value": 5.0},
        ]
    )
    with pytest.raises(ValueError, match="duplicate"):
        run_path_scenario(
            panel,
            posterior,
            constraints,
            scenario_name="duplicate",
        )


def test_unknown_variable_fails_closed() -> None:
    panel, posterior = fitted()
    constraints = pd.DataFrame(
        [{"horizon": 1, "variable": "unknown", "value": 1.0}]
    )
    with pytest.raises(ValueError, match="unknown variable"):
        run_path_scenario(
            panel,
            posterior,
            constraints,
            scenario_name="bad variable",
        )


@pytest.mark.parametrize("horizon", [0, 9])
def test_out_of_range_horizon_fails_closed(horizon: int) -> None:
    panel, posterior = fitted()
    constraints = pd.DataFrame(
        [
            {
                "horizon": horizon,
                "variable": "policy_rate",
                "value": 4.0,
            }
        ]
    )
    with pytest.raises(ValueError, match="between 1 and 8"):
        run_path_scenario(
            panel,
            posterior,
            constraints,
            scenario_name="bad horizon",
        )


@pytest.mark.parametrize("value", [np.nan, np.inf])
def test_nonfinite_constraint_fails_closed(value: float) -> None:
    panel, posterior = fitted()
    constraints = pd.DataFrame(
        [
            {
                "horizon": 1,
                "variable": "policy_rate",
                "value": value,
            }
        ]
    )
    with pytest.raises(ValueError, match="finite"):
        run_path_scenario(
            panel,
            posterior,
            constraints,
            scenario_name="bad value",
        )


def test_exact_estimation_panel_identity_is_required() -> None:
    panel, posterior = fitted()
    altered = panel.copy()
    altered.iloc[-1, 0] += 0.01

    with pytest.raises(ValueError, match="exact posterior estimation panel"):
        run_path_scenario(
            altered,
            posterior,
            pd.DataFrame(
                [
                    {
                        "horizon": 1,
                        "variable": "policy_rate",
                        "value": 4.0,
                    }
                ]
            ),
            scenario_name="wrong panel",
        )


def test_scenario_does_not_mutate_panel_or_posterior() -> None:
    panel, posterior = fitted()
    panel_before = panel.copy(deep=True)
    mean_before = posterior.posterior_mean.copy()

    run_path_scenario(
        panel,
        posterior,
        policy_constraint(panel, posterior),
        scenario_name="immutability",
    )

    pd.testing.assert_frame_equal(panel, panel_before)
    np.testing.assert_array_equal(
        posterior.posterior_mean,
        mean_before,
    )

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.model import VARIABLES, candidate_grid, fit_bvar
from macropulse.bvar.probabilistic import DEFAULT_SEED, INTERVAL_COVERAGES, simulate_posterior_predictive


def synthetic_panel(periods: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(12345)
    values = np.zeros((periods, 4), dtype=float)
    values[0] = [2.0, 2.2, 4.5, 3.0]
    transition = np.diag([0.25, 0.35, 0.85, 0.75])
    intercept = np.array([1.4, 1.3, 0.65, 0.8])
    noise_scale = np.array([0.35, 0.30, 0.08, 0.10])
    for t in range(1, periods):
        values[t] = intercept + values[t - 1] @ transition.T + rng.normal(scale=noise_scale, size=4)
    return pd.DataFrame(values, index=pd.period_range("2000Q1", periods=periods, freq="Q"), columns=list(VARIABLES))


def simulation(seed: int = DEFAULT_SEED, simulations: int = 300):
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    result = simulate_posterior_predictive(panel, posterior, simulations=simulations, seed=seed)
    return panel, posterior, result


def test_same_seed_is_reproducible() -> None:
    _, _, first = simulation()
    _, _, second = simulation()
    assert first.draw_hash == second.draw_hash
    np.testing.assert_array_equal(first.draws, second.draws)
    pd.testing.assert_frame_equal(first.summary, second.summary)


def test_different_seed_changes_draws() -> None:
    _, _, first = simulation(seed=11)
    _, _, second = simulation(seed=12)
    assert first.draw_hash != second.draw_hash
    assert not np.array_equal(first.draws, second.draws)


def test_draw_shape_and_horizons_are_governed() -> None:
    _, _, result = simulation(simulations=200)
    assert result.draws.shape == (200, 4, 4)
    assert result.horizons == (1, 2, 4, 8)
    assert result.variables == tuple(VARIABLES)
    assert len(result.summary) == 16


def test_summary_intervals_are_nested() -> None:
    _, _, result = simulation(simulations=500)
    for row in result.summary.itertuples(index=False):
        assert row.lower_95 <= row.lower_80 <= row.lower_50
        assert row.lower_50 <= row.median <= row.upper_50
        assert row.upper_50 <= row.upper_80 <= row.upper_95


def test_summary_is_finite() -> None:
    _, _, result = simulation(simulations=200)
    numeric = result.summary[["mean","median","std","lower_50","upper_50","lower_80","upper_80","lower_95","upper_95"]].to_numpy(dtype=float)
    assert np.isfinite(numeric).all()


def test_target_quarter_labels_match_horizons() -> None:
    _, _, result = simulation(simulations=200)
    rows = result.summary[result.summary["variable"] == "real_gdp_growth"]
    assert rows["target_quarter"].tolist() == ["2020Q1","2020Q2","2020Q4","2021Q4"]


def test_exact_estimation_panel_identity_is_required() -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    altered = panel.copy()
    altered.iloc[-1, 0] += 0.01
    with pytest.raises(ValueError, match="exact posterior estimation panel"):
        simulate_posterior_predictive(altered, posterior, simulations=100)


@pytest.mark.parametrize("bad", [0, 1, 99])
def test_too_few_simulations_fail_closed(bad: int) -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    with pytest.raises(ValueError, match="at least 100"):
        simulate_posterior_predictive(panel, posterior, simulations=bad)


@pytest.mark.parametrize("bad", [-1, 2**63])
def test_invalid_seed_fails_closed(bad: int) -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    with pytest.raises(ValueError, match="0 <= seed"):
        simulate_posterior_predictive(panel, posterior, simulations=100, seed=bad)


def test_simulation_does_not_mutate_panel_or_posterior() -> None:
    panel = synthetic_panel()
    panel_original = panel.copy(deep=True)
    posterior = fit_bvar(panel, candidate_grid()[0])
    mean_original = posterior.posterior_mean.copy()
    scale_original = posterior.posterior_iw_scale.copy()
    simulate_posterior_predictive(panel, posterior, simulations=100)
    pd.testing.assert_frame_equal(panel, panel_original)
    np.testing.assert_array_equal(posterior.posterior_mean, mean_original)
    np.testing.assert_array_equal(posterior.posterior_iw_scale, scale_original)


def test_interval_coverages_are_frozen() -> None:
    assert INTERVAL_COVERAGES == (0.50, 0.80, 0.95)

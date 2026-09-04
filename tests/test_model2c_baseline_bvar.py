from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.model import (
    VARIABLES,
    BVARCandidate,
    candidate_grid,
    fit_bvar,
    point_forecast,
)


def synthetic_panel(periods: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(12345)
    values = np.zeros((periods, 4), dtype=float)
    values[0] = [2.0, 2.2, 4.5, 3.0]

    transition = np.diag([0.25, 0.35, 0.85, 0.75])
    intercept = np.array([1.4, 1.3, 0.65, 0.8])
    noise_scale = np.array([0.35, 0.30, 0.08, 0.10])

    for t in range(1, periods):
        values[t] = (
            intercept
            + values[t - 1] @ transition.T
            + rng.normal(scale=noise_scale, size=4)
        )

    return pd.DataFrame(
        values,
        index=pd.period_range("2000Q1", periods=periods, freq="Q"),
        columns=list(VARIABLES),
    )


def test_candidate_grid_is_frozen_six_candidates() -> None:
    grid = candidate_grid()
    assert len(grid) == 6
    assert {(x.lags, x.shrinkage) for x in grid} == {
        (2, 0.1), (2, 0.2), (2, 0.4),
        (4, 0.1), (4, 0.2), (4, 0.4),
    }
    assert len({x.candidate_id for x in grid}) == 6


def test_prior_means_match_transformation_status() -> None:
    panel = synthetic_panel()
    candidate = candidate_grid()[0]
    posterior = fit_bvar(panel, candidate)

    assert posterior.prior_mean[1, 0] == pytest.approx(0.0)
    assert posterior.prior_mean[2, 1] == pytest.approx(0.0)
    assert posterior.prior_mean[3, 2] == pytest.approx(1.0)
    assert posterior.prior_mean[4, 3] == pytest.approx(1.0)


def test_fit_shapes_and_covariance_are_valid() -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[-1])

    assert posterior.posterior_mean.shape == (17, 4)
    assert posterior.posterior_covariance.shape == (17, 17)
    assert posterior.expected_sigma.shape == (4, 4)
    assert np.isfinite(posterior.expected_sigma).all()
    assert np.linalg.eigvalsh(posterior.expected_sigma).min() > 0
    assert np.isfinite(posterior.companion_spectral_radius)


def test_smaller_lambda_has_tighter_lag_prior() -> None:
    panel = synthetic_panel()
    small = fit_bvar(panel, candidate_grid()[0])
    large = fit_bvar(panel, candidate_grid()[2])

    assert small.prior_covariance[1, 1] < large.prior_covariance[1, 1]


def test_point_forecast_has_governed_horizons() -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])
    forecast = point_forecast(panel, posterior)

    assert forecast["horizon"].tolist() == [1, 2, 4, 8]
    assert forecast["target_quarter"].tolist() == [
        "2020Q1", "2020Q2", "2020Q4", "2021Q4"
    ]
    assert np.isfinite(
        forecast.loc[:, list(VARIABLES)].to_numpy(dtype=float)
    ).all()


def test_point_forecast_requires_exact_estimation_panel() -> None:
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[0])

    altered = panel.copy()
    altered.iloc[-1, 0] += 0.01
    with pytest.raises(ValueError, match="exact posterior estimation panel"):
        point_forecast(altered, posterior)


def test_insufficient_effective_sample_fails_closed() -> None:
    panel = synthetic_panel(periods=24)
    with pytest.raises(ValueError, match="Insufficient effective observations"):
        fit_bvar(panel, candidate_grid()[0])


def test_noncontiguous_panel_fails_closed() -> None:
    panel = synthetic_panel().drop(pd.Period("2005Q1", freq="Q"))
    with pytest.raises(ValueError, match="contiguous"):
        fit_bvar(panel, candidate_grid()[0])


def test_candidate_outside_grid_fails_closed() -> None:
    panel = synthetic_panel()
    candidate = BVARCandidate(
        lags=3,
        shrinkage=0.2,
        candidate_id="invalid",
    )
    with pytest.raises(ValueError, match="outside frozen Model 2C grid"):
        fit_bvar(panel, candidate)


def test_fit_does_not_mutate_panel() -> None:
    panel = synthetic_panel()
    original = panel.copy(deep=True)
    fit_bvar(panel, candidate_grid()[0])
    pd.testing.assert_frame_equal(panel, original)

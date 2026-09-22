from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.model import VARIABLES, candidate_grid, fit_bvar
from macropulse.bvar.structural import (
    IDENTIFICATION,
    STRUCTURAL_HORIZONS,
    STRUCTURAL_ORDER,
    _lag_matrices,
    structural_analysis,
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
    innovation_covariance = np.array(
        [
            [0.20, 0.03, -0.01, 0.00],
            [0.03, 0.16, 0.01, 0.02],
            [-0.01, 0.01, 0.03, -0.005],
            [0.00, 0.02, -0.005, 0.05],
        ],
        dtype=float,
    )
    root = np.linalg.cholesky(innovation_covariance)

    for t in range(1, periods):
        values[t] = (
            intercept
            + transition @ values[t - 1]
            + root @ rng.standard_normal(4)
        )

    return pd.DataFrame(
        values,
        index=pd.period_range("2000Q1", periods=periods, freq="Q"),
        columns=list(VARIABLES),
    )


def fitted(candidate_index: int = 0):
    panel = synthetic_panel()
    posterior = fit_bvar(panel, candidate_grid()[candidate_index])
    return panel, posterior, structural_analysis(posterior)


def test_structural_order_and_horizons_are_frozen() -> None:
    assert STRUCTURAL_ORDER == (
        "real_gdp_growth",
        "core_pce_inflation",
        "unemployment_rate",
        "policy_rate",
    )
    assert STRUCTURAL_HORIZONS == (1, 4, 8, 12)
    assert IDENTIFICATION == "recursive_cholesky"


def test_impact_matrix_respects_recursive_zero_restrictions() -> None:
    _, _, result = fitted()
    assert np.allclose(
        np.triu(result.impact_matrix, k=1),
        0.0,
        atol=1e-12,
    )
    assert bool((np.diag(result.impact_matrix) > 0).all())


def test_irf_has_expected_shape_and_is_finite() -> None:
    _, _, result = fitted()
    assert len(result.irf) == 4 * 4 * 4
    assert set(result.irf["horizon"]) == {1, 4, 8, 12}
    assert np.isfinite(
        result.irf["response_value"].to_numpy(dtype=float)
    ).all()


def test_fevd_has_expected_shape_and_is_finite() -> None:
    _, _, result = fitted()
    assert len(result.fevd) == 4 * 4 * 4
    assert set(result.fevd["horizon"]) == {1, 4, 8, 12}
    assert np.isfinite(result.fevd["share"].to_numpy(dtype=float)).all()


def test_fevd_shares_sum_to_one() -> None:
    _, _, result = fitted()
    totals = (
        result.fevd.groupby(["horizon", "response"])["share"].sum()
    )
    np.testing.assert_allclose(
        totals.to_numpy(dtype=float),
        1.0,
        rtol=0.0,
        atol=1e-12,
    )


def test_fevd_shares_are_bounded() -> None:
    _, _, result = fitted()
    shares = result.fevd["share"].to_numpy(dtype=float)
    assert bool((shares >= -1e-12).all())
    assert bool((shares <= 1.0 + 1e-12).all())


def test_horizon_one_irf_matches_a1_times_impact() -> None:
    _, posterior, result = fitted()
    a1 = _lag_matrices(posterior)[0]
    expected = a1 @ result.impact_matrix

    actual = (
        result.irf[result.irf["horizon"] == 1]
        .pivot(index="response", columns="shock", values="response_value")
        .reindex(index=STRUCTURAL_ORDER, columns=STRUCTURAL_ORDER)
        .to_numpy(dtype=float)
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


def test_horizon_one_fevd_uses_impact_variance() -> None:
    _, _, result = fitted()
    squared = result.impact_matrix**2
    expected = squared / squared.sum(axis=1)[:, None]

    actual = (
        result.fevd[result.fevd["horizon"] == 1]
        .pivot(index="response", columns="shock", values="share")
        .reindex(index=STRUCTURAL_ORDER, columns=STRUCTURAL_ORDER)
        .to_numpy(dtype=float)
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)


def test_analysis_is_deterministic() -> None:
    _, posterior, first = fitted()
    second = structural_analysis(posterior)

    np.testing.assert_array_equal(first.impact_matrix, second.impact_matrix)
    pd.testing.assert_frame_equal(first.irf, second.irf)
    pd.testing.assert_frame_equal(first.fevd, second.fevd)


def test_structural_analysis_does_not_mutate_posterior() -> None:
    _, posterior, _ = fitted()
    mean_before = posterior.posterior_mean.copy()
    sigma_before = posterior.expected_sigma.copy()

    structural_analysis(posterior)

    np.testing.assert_array_equal(posterior.posterior_mean, mean_before)
    np.testing.assert_array_equal(posterior.expected_sigma, sigma_before)


def test_wrong_variable_order_fails_closed() -> None:
    _, posterior, _ = fitted()
    altered = replace(
        posterior,
        variables=tuple(reversed(posterior.variables)),
    )

    with pytest.raises(ValueError, match="ordering"):
        structural_analysis(altered)


def test_non_positive_definite_covariance_fails_closed() -> None:
    _, posterior, _ = fitted()
    bad_sigma = posterior.expected_sigma.copy()
    bad_sigma[0, 0] = -1.0
    altered = replace(posterior, expected_sigma=bad_sigma)

    with pytest.raises(ValueError, match="positive definite"):
        structural_analysis(altered)


def test_all_six_candidates_generate_structural_results() -> None:
    panel = synthetic_panel()
    seen = set()

    for candidate in candidate_grid():
        posterior = fit_bvar(panel, candidate)
        result = structural_analysis(posterior)
        seen.add(result.candidate_id)

        assert np.isfinite(
            result.irf["response_value"].to_numpy(dtype=float)
        ).all()
        assert np.isfinite(
            result.fevd["share"].to_numpy(dtype=float)
        ).all()

    assert len(seen) == 6

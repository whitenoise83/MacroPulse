import numpy as np
import pandas as pd
import pytest

from macropulse.slack.state_space import (
    MIN_OBSERVATIONS,
    PotentialOutputUCModel,
    _pacf_to_ar2,
    ar2_is_stationary,
    fit_state_space,
)


def synthetic_log_gdp(n=120, seed=7):
    rng = np.random.default_rng(seed)
    potential = np.empty(n)
    growth = np.empty(n)
    gap = np.empty(n)
    potential[0] = np.log(100.0)
    growth[0] = 0.005
    gap[0] = 0.0
    gap_lag = 0.0
    for t in range(1, n):
        growth[t] = growth[t - 1] + rng.normal(0.0, 0.00025)
        potential[t] = potential[t - 1] + growth[t - 1]
        new_gap = 0.65 * gap[t - 1] - 0.15 * gap_lag + rng.normal(0.0, 0.004)
        gap_lag = gap[t - 1]
        gap[t] = new_gap
    idx = pd.period_range("1995Q1", periods=n, freq="Q")
    return pd.Series(potential + gap, index=idx, name="real_gdp_log")


def test_pacf_map_always_produces_stationary_ar2():
    for k1, k2 in [(0.0, 0.0), (0.8, -0.4), (-0.7, 0.5), (0.95, 0.9)]:
        phi1, phi2 = _pacf_to_ar2(k1, k2)
        assert ar2_is_stationary(phi1, phi2)


def test_known_stationary_and_nonstationary_ar2_cases():
    assert ar2_is_stationary(0.65, -0.15)
    assert not ar2_is_stationary(1.2, 0.1)


def test_parameter_transform_positive_variances_and_stationary_gap():
    model = PotentialOutputUCModel(synthetic_log_gdp(80))
    constrained = model.start_params
    assert np.all(constrained[:2] > 0.0)
    assert ar2_is_stationary(constrained[2], constrained[3])
    retransformed = model.transform_params(model.untransform_params(constrained))
    assert np.allclose(constrained, retransformed, atol=1e-10, rtol=1e-10)


def test_transform_round_trip():
    model = PotentialOutputUCModel(synthetic_log_gdp(80))
    constrained = model.start_params
    recovered = model.transform_params(model.untransform_params(constrained))
    assert np.allclose(constrained, recovered, atol=1e-10, rtol=1e-10)


def test_short_sample_rejected():
    with pytest.raises(ValueError, match="At least"):
        PotentialOutputUCModel(synthetic_log_gdp(MIN_OBSERVATIONS - 1))


def test_nonconsecutive_quarters_rejected():
    y = synthetic_log_gdp(60).drop(pd.Period("2000Q1", freq="Q"))
    with pytest.raises(ValueError, match="consecutive"):
        PotentialOutputUCModel(y)


def test_nonfinite_input_rejected():
    y = synthetic_log_gdp(60)
    y.iloc[10] = np.nan
    with pytest.raises(ValueError, match="finite"):
        PotentialOutputUCModel(y)


def test_fit_returns_separately_labelled_filtered_and_smoothed_estimates():
    fit = fit_state_space(synthetic_log_gdp(120), maxiter=500)
    assert set(fit.estimates["estimate_class"].unique()) == {
        "filtered_full_sample_parameters", "smoothed_revised"
    }
    assert fit.diagnostics.converged is True
    assert np.isfinite(fit.diagnostics.log_likelihood)
    assert fit.diagnostics.sigma_potential == 0.0
    assert fit.diagnostics.sigma_trend_growth > 0.0
    assert fit.diagnostics.sigma_gap > 0.0
    assert ar2_is_stationary(fit.diagnostics.phi1, fit.diagnostics.phi2)


def test_output_gap_identity_holds_for_both_estimate_classes():
    fit = fit_state_space(synthetic_log_gdp(120), maxiter=500)
    f = fit.estimates
    assert np.allclose(
        f["output_gap_pct"],
        100.0 * (f["observed_log_output"] - f["potential_log_output"]),
    )


def test_potential_level_is_exponentiated_log_potential():
    fit = fit_state_space(synthetic_log_gdp(120), maxiter=500)
    f = fit.estimates
    assert np.allclose(f["potential_output_level"], np.exp(f["potential_log_output"]))


def test_filtered_and_smoothed_labels_are_not_interchangeable():
    fit = fit_state_space(synthetic_log_gdp(120), maxiter=500)
    f = fit.estimates
    filtered = f[f["estimate_class"].eq("filtered_full_sample_parameters")]
    smoothed = f[f["estimate_class"].eq("smoothed_revised")]
    assert len(filtered) == len(smoothed) == 120
    assert filtered.index.equals(smoothed.index)
    assert not np.allclose(
        filtered["potential_log_output"].iloc[:-1],
        smoothed["potential_log_output"].iloc[:-1],
    )

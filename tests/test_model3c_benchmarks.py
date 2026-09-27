import numpy as np
import pandas as pd
import pytest

from macropulse.slack.benchmarks import (
    deterministic_linear_trend,
    endpoint_hamilton,
    endpoint_one_sided_hp,
    hamilton_cycle,
    hp_filter,
    pseudo_real_time_endpoints,
)


def quarterly_series(n=80, shock=0.0):
    idx = pd.period_range("2000Q1", periods=n, freq="Q")
    t = np.arange(n, dtype=float)
    values = 9.0 + 0.005 * t + 0.01 * np.sin(t / 3.0)
    if shock:
        values[-1] += shock
    return pd.Series(values, index=idx, name="real_gdp_log")


def test_linear_trend_exact_for_linear_data():
    idx = pd.period_range("2000Q1", periods=40, freq="Q")
    y = pd.Series(8.0 + 0.01 * np.arange(40), index=idx)
    trend = deterministic_linear_trend(y)
    assert np.allclose(trend.to_numpy(), y.to_numpy(), atol=1e-12)


def test_hp_preserves_linear_series():
    idx = pd.period_range("2000Q1", periods=40, freq="Q")
    y = pd.Series(8.0 + 0.01 * np.arange(40), index=idx)
    trend = hp_filter(y)
    assert np.allclose(trend.to_numpy(), y.to_numpy(), atol=1e-10)


def test_one_sided_endpoint_does_not_use_future_data():
    y = quarterly_series(60)
    early = endpoint_one_sided_hp(y.iloc[:40])
    altered_future = y.copy()
    altered_future.iloc[40:] += 10.0
    repeated = endpoint_one_sided_hp(altered_future.iloc[:40])
    assert early == repeated


def test_pseudo_real_time_origin_estimate_is_immutable_to_future_extension():
    y = quarterly_series(60)
    first = pseudo_real_time_endpoints(y.iloc[:50], "one_sided_hp_filter")
    extended = y.copy()
    extended.iloc[50:] += 5.0
    second = pseudo_real_time_endpoints(extended, "one_sided_hp_filter")
    origin = first.iloc[-1]["estimate_origin"]
    a = first[first["estimate_origin"] == origin].iloc[0]
    b = second[second["estimate_origin"] == origin].iloc[0]
    assert np.isclose(a["potential_log_output"], b["potential_log_output"])


def test_hamilton_cycle_has_expected_alignment():
    y = quarterly_series(60)
    cycle = hamilton_cycle(y)
    assert cycle.index[0] == y.index[11]  # p-1 + h = 3 + 8
    assert cycle.index[-1] == y.index[-1]


def test_hamilton_endpoint_identity():
    y = quarterly_series(60)
    est = endpoint_hamilton(y)
    assert np.isclose(
        est.output_gap_pct,
        100.0 * (est.observed_log_output - est.potential_log_output),
    )


def test_nonconsecutive_quarters_fail_closed():
    y = quarterly_series(30).drop(quarterly_series(30).index[10])
    with pytest.raises(ValueError, match="consecutive"):
        deterministic_linear_trend(y)


def test_short_sample_fails_closed():
    y = quarterly_series(10)
    with pytest.raises(ValueError, match="At least 20"):
        hp_filter(y)


def test_unsupported_pseudo_real_time_benchmark_rejected():
    y = quarterly_series(30)
    with pytest.raises(ValueError, match="Unsupported"):
        pseudo_real_time_endpoints(y, "hp_filter")

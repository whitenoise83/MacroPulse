from __future__ import annotations

from dataclasses import dataclass
from math import exp

import numpy as np
import pandas as pd


MIN_OBSERVATIONS = 20
HP_LAMBDA_QUARTERLY = 1600.0
HAMILTON_HORIZON = 8
HAMILTON_LAGS = 4


@dataclass(frozen=True)
class BenchmarkEstimate:
    benchmark_id: str
    estimate_origin: str
    observed_log_output: float
    potential_log_output: float
    potential_output_level: float
    output_gap_pct: float


def _validate_series(y: pd.Series, minimum: int = MIN_OBSERVATIONS) -> pd.Series:
    if not isinstance(y.index, pd.PeriodIndex) or y.index.freqstr[0] != "Q":
        raise ValueError("real_gdp_log must use a quarterly PeriodIndex.")
    y = y.astype(float).sort_index()
    if len(y) < minimum:
        raise ValueError(f"At least {minimum} observations are required.")
    if y.index.has_duplicates:
        raise ValueError("Quarter index contains duplicates.")
    ordinals = np.array([p.ordinal for p in y.index])
    if len(ordinals) > 1 and not np.all(np.diff(ordinals) == 1):
        raise ValueError("Quarter index must be consecutive.")
    if not np.isfinite(y.to_numpy()).all():
        raise ValueError("real_gdp_log must contain only finite values.")
    return y


def _result(benchmark_id: str, origin: pd.Period, observed: float, potential: float) -> BenchmarkEstimate:
    return BenchmarkEstimate(
        benchmark_id=benchmark_id,
        estimate_origin=str(origin),
        observed_log_output=float(observed),
        potential_log_output=float(potential),
        potential_output_level=float(exp(potential)),
        output_gap_pct=float(100.0 * (observed - potential)),
    )


def deterministic_linear_trend(y: pd.Series) -> pd.Series:
    y = _validate_series(y)
    x = np.column_stack([np.ones(len(y)), np.arange(len(y), dtype=float)])
    beta, *_ = np.linalg.lstsq(x, y.to_numpy(), rcond=None)
    return pd.Series(x @ beta, index=y.index, name="potential_log_output")


def _hp_trend(y: pd.Series, lamb: float = HP_LAMBDA_QUARTERLY) -> pd.Series:
    y = _validate_series(y)
    n = len(y)
    eye = np.eye(n)
    d = np.zeros((n - 2, n))
    for i in range(n - 2):
        d[i, i] = 1.0
        d[i, i + 1] = -2.0
        d[i, i + 2] = 1.0
    trend = np.linalg.solve(eye + float(lamb) * (d.T @ d), y.to_numpy())
    return pd.Series(trend, index=y.index, name="potential_log_output")


def hp_filter(y: pd.Series, lamb: float = HP_LAMBDA_QUARTERLY) -> pd.Series:
    """Conventional two-sided HP diagnostic benchmark."""
    return _hp_trend(y, lamb=lamb)


def endpoint_linear_trend(y: pd.Series) -> BenchmarkEstimate:
    y = _validate_series(y)
    trend = deterministic_linear_trend(y)
    return _result("deterministic_linear_trend", y.index[-1], y.iloc[-1], trend.iloc[-1])


def endpoint_hp(y: pd.Series, lamb: float = HP_LAMBDA_QUARTERLY) -> BenchmarkEstimate:
    y = _validate_series(y)
    trend = hp_filter(y, lamb=lamb)
    return _result("hp_filter", y.index[-1], y.iloc[-1], trend.iloc[-1])


def endpoint_one_sided_hp(y: pd.Series, lamb: float = HP_LAMBDA_QUARTERLY) -> BenchmarkEstimate:
    """Fit HP only through the supplied origin and retain its terminal trend."""
    y = _validate_series(y)
    trend = _hp_trend(y, lamb=lamb)
    return _result("one_sided_hp_filter", y.index[-1], y.iloc[-1], trend.iloc[-1])


def hamilton_cycle(
    y: pd.Series,
    horizon: int = HAMILTON_HORIZON,
    lags: int = HAMILTON_LAGS,
) -> pd.Series:
    y = _validate_series(y, minimum=max(MIN_OBSERVATIONS, horizon + lags + 1))
    values = y.to_numpy()
    rows = []
    targets = []
    target_positions = []
    for t in range(lags - 1, len(y) - horizon):
        rows.append([1.0] + [values[t - j] for j in range(lags)])
        targets.append(values[t + horizon])
        target_positions.append(t + horizon)
    x = np.asarray(rows, dtype=float)
    target = np.asarray(targets, dtype=float)
    beta, *_ = np.linalg.lstsq(x, target, rcond=None)
    residual = target - x @ beta
    index = pd.PeriodIndex([y.index[pos] for pos in target_positions], freq="Q")
    return pd.Series(residual, index=index, name="hamilton_cycle")


def endpoint_hamilton(
    y: pd.Series,
    horizon: int = HAMILTON_HORIZON,
    lags: int = HAMILTON_LAGS,
) -> BenchmarkEstimate:
    y = _validate_series(y, minimum=max(MIN_OBSERVATIONS, horizon + lags + 1))
    cycle = hamilton_cycle(y, horizon=horizon, lags=lags)
    origin = cycle.index[-1]
    observed = float(y.loc[origin])
    potential = observed - float(cycle.iloc[-1])
    return _result("hamilton_regression", origin, observed, potential)


def pseudo_real_time_endpoints(
    y: pd.Series,
    benchmark_id: str,
    start_observations: int = MIN_OBSERVATIONS,
) -> pd.DataFrame:
    """Re-estimate a benchmark recursively and retain only each origin endpoint."""
    y = _validate_series(y, minimum=start_observations)
    records = []
    for n in range(start_observations, len(y) + 1):
        sample = y.iloc[:n]
        if benchmark_id == "deterministic_linear_trend":
            est = endpoint_linear_trend(sample)
        elif benchmark_id == "one_sided_hp_filter":
            est = endpoint_one_sided_hp(sample)
        elif benchmark_id == "hamilton_regression":
            if n < max(MIN_OBSERVATIONS, HAMILTON_HORIZON + HAMILTON_LAGS + 1):
                continue
            est = endpoint_hamilton(sample)
        else:
            raise ValueError("Unsupported pseudo-real-time benchmark: " + benchmark_id)
        records.append(est.__dict__)
    return pd.DataFrame.from_records(records)

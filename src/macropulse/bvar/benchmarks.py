from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macropulse.bvar.model import VARIABLES, _validate_panel


BENCHMARK_AR4 = "benchmark::univariate_ar4"
BENCHMARK_VAR4 = "benchmark::classical_var4"
BENCHMARK_SIMPLE = "benchmark::historical_mean_random_walk"
BENCHMARK_IDS = (BENCHMARK_AR4, BENCHMARK_VAR4, BENCHMARK_SIMPLE)
BENCHMARK_LAGS = 4


@dataclass(frozen=True)
class BenchmarkForecast:
    model_id: str
    horizons: tuple[int, ...]
    variables: tuple[str, ...]
    point: np.ndarray
    draws: np.ndarray


def _validate_horizons(horizons: tuple[int, ...]) -> tuple[int, ...]:
    requested = tuple(int(value) for value in horizons)
    if not requested:
        raise ValueError("At least one benchmark horizon is required.")
    if any(value <= 0 for value in requested):
        raise ValueError("Benchmark horizons must be positive.")
    if tuple(sorted(set(requested))) != requested:
        raise ValueError(
            "Benchmark horizons must be unique and strictly increasing."
        )
    return requested


def _validate_simulations(simulations: int) -> int:
    if isinstance(simulations, bool) or not isinstance(
        simulations, (int, np.integer)
    ):
        raise ValueError("Benchmark simulation count must be an integer.")
    value = int(simulations)
    if value < 100:
        raise ValueError("Benchmark simulation count must be at least 100.")
    return value


def _fit_univariate_ar(
    values: np.ndarray,
    lags: int = BENCHMARK_LAGS,
) -> tuple[np.ndarray, float]:
    y = np.asarray(values, dtype=float)
    rows = []
    targets = []
    for t in range(lags, len(y)):
        rows.append([1.0, *[float(y[t - lag]) for lag in range(1, lags + 1)]])
        targets.append(float(y[t]))
    x = np.asarray(rows, dtype=float)
    target = np.asarray(targets, dtype=float)
    minimum = max(24, 2 * x.shape[1])
    if len(target) < minimum:
        raise ValueError("Insufficient observations for AR(4) benchmark.")
    beta, _, _, _ = np.linalg.lstsq(x, target, rcond=None)
    residual = target - x @ beta
    dof = len(residual) - x.shape[1]
    if dof <= 0:
        raise ValueError("AR(4) residual variance degrees of freedom invalid.")
    variance = float(residual @ residual / dof)
    if not np.isfinite(variance) or variance <= 1e-12:
        raise ValueError("AR(4) residual variance must be positive and finite.")
    return beta, float(np.sqrt(variance))


def simulate_univariate_ar4(
    panel: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    simulations: int,
    seed: int,
) -> BenchmarkForecast:
    frame = _validate_panel(panel)
    requested = _validate_horizons(horizons)
    n_simulations = _validate_simulations(simulations)
    rng = np.random.default_rng(int(seed))
    m = len(VARIABLES)
    max_horizon = max(requested)

    betas = []
    sigmas = []
    values = frame.to_numpy(dtype=float)
    for variable_index in range(m):
        beta, sigma = _fit_univariate_ar(values[:, variable_index])
        betas.append(beta)
        sigmas.append(sigma)

    deterministic = np.empty((max_horizon, m), dtype=float)
    for variable_index in range(m):
        history = list(values[:, variable_index].astype(float))
        beta = betas[variable_index]
        for step in range(max_horizon):
            design = np.array(
                [1.0, *[history[-lag] for lag in range(1, BENCHMARK_LAGS + 1)]],
                dtype=float,
            )
            value = float(design @ beta)
            if not np.isfinite(value):
                raise ValueError("AR(4) deterministic forecast became non-finite.")
            history.append(value)
            deterministic[step, variable_index] = value

    draws_full = np.empty((n_simulations, max_horizon, m), dtype=float)
    for variable_index in range(m):
        history = np.empty(
            (n_simulations, BENCHMARK_LAGS + max_horizon),
            dtype=float,
        )
        history[:, :BENCHMARK_LAGS] = values[
            -BENCHMARK_LAGS:, variable_index
        ][None, :]
        beta = betas[variable_index]
        sigma = sigmas[variable_index]
        for step in range(max_horizon):
            design = np.ones((n_simulations, BENCHMARK_LAGS + 1), dtype=float)
            for lag in range(1, BENCHMARK_LAGS + 1):
                design[:, lag] = history[
                    :, BENCHMARK_LAGS + step - lag
                ]
            future = design @ beta + rng.normal(
                loc=0.0,
                scale=sigma,
                size=n_simulations,
            )
            history[:, BENCHMARK_LAGS + step] = future
            draws_full[:, step, variable_index] = future

    positions = [value - 1 for value in requested]
    return BenchmarkForecast(
        model_id=BENCHMARK_AR4,
        horizons=requested,
        variables=tuple(VARIABLES),
        point=deterministic[positions, :].copy(),
        draws=draws_full[:, positions, :].copy(),
    )


def _fit_classical_var(
    frame: pd.DataFrame,
    lags: int = BENCHMARK_LAGS,
) -> tuple[np.ndarray, np.ndarray]:
    values = frame.to_numpy(dtype=float)
    m = len(VARIABLES)
    rows = []
    targets = []
    for t in range(lags, len(values)):
        row = [1.0]
        for lag in range(1, lags + 1):
            row.extend(values[t - lag].tolist())
        rows.append(row)
        targets.append(values[t].tolist())
    x = np.asarray(rows, dtype=float)
    y = np.asarray(targets, dtype=float)
    minimum = max(24, 2 * x.shape[1])
    if len(y) < minimum:
        raise ValueError("Insufficient observations for classical VAR(4).")
    beta, _, _, _ = np.linalg.lstsq(x, y, rcond=None)
    residual = y - x @ beta
    dof = len(residual) - x.shape[1]
    if dof <= 0:
        raise ValueError("Classical VAR(4) covariance degrees of freedom invalid.")
    covariance = residual.T @ residual / dof
    covariance = (covariance + covariance.T) / 2.0
    if covariance.shape != (m, m):
        raise ValueError("Classical VAR(4) covariance has unexpected shape.")
    try:
        np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Classical VAR(4) residual covariance is not positive definite."
        ) from exc
    return beta, covariance


def simulate_classical_var4(
    panel: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    simulations: int,
    seed: int,
) -> BenchmarkForecast:
    frame = _validate_panel(panel)
    requested = _validate_horizons(horizons)
    n_simulations = _validate_simulations(simulations)
    rng = np.random.default_rng(int(seed))
    values = frame.to_numpy(dtype=float)
    m = len(VARIABLES)
    max_horizon = max(requested)
    beta, covariance = _fit_classical_var(frame)
    root = np.linalg.cholesky(covariance)

    history_det = [row.copy() for row in values]
    deterministic = []
    for _ in range(max_horizon):
        design = [1.0]
        for lag in range(1, BENCHMARK_LAGS + 1):
            design.extend(history_det[-lag].tolist())
        future = np.asarray(design, dtype=float) @ beta
        if not np.isfinite(future).all():
            raise ValueError("Classical VAR(4) deterministic forecast non-finite.")
        history_det.append(future)
        deterministic.append(future)
    deterministic = np.asarray(deterministic, dtype=float)

    k = beta.shape[0]
    history = np.empty(
        (n_simulations, BENCHMARK_LAGS + max_horizon, m),
        dtype=float,
    )
    history[:, :BENCHMARK_LAGS, :] = values[-BENCHMARK_LAGS:, :][None, :, :]
    draws_full = np.empty((n_simulations, max_horizon, m), dtype=float)

    for step in range(max_horizon):
        design = np.ones((n_simulations, k), dtype=float)
        offset = 1
        for lag in range(1, BENCHMARK_LAGS + 1):
            design[:, offset:offset + m] = history[
                :, BENCHMARK_LAGS + step - lag, :
            ]
            offset += m
        conditional = design @ beta
        innovation = rng.standard_normal((n_simulations, m)) @ root.T
        future = conditional + innovation
        if not np.isfinite(future).all():
            raise ValueError("Classical VAR(4) simulation became non-finite.")
        history[:, BENCHMARK_LAGS + step, :] = future
        draws_full[:, step, :] = future

    positions = [value - 1 for value in requested]
    return BenchmarkForecast(
        model_id=BENCHMARK_VAR4,
        horizons=requested,
        variables=tuple(VARIABLES),
        point=deterministic[positions, :].copy(),
        draws=draws_full[:, positions, :].copy(),
    )


def simulate_historical_mean_random_walk(
    panel: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    simulations: int,
    seed: int,
) -> BenchmarkForecast:
    frame = _validate_panel(panel)
    requested = _validate_horizons(horizons)
    n_simulations = _validate_simulations(simulations)
    rng = np.random.default_rng(int(seed))
    values = frame.to_numpy(dtype=float)
    m = len(VARIABLES)
    max_horizon = max(requested)

    deterministic = np.empty((max_horizon, m), dtype=float)
    draws_full = np.empty((n_simulations, max_horizon, m), dtype=float)

    for variable_index, variable in enumerate(VARIABLES):
        series = values[:, variable_index]
        if variable in ("real_gdp_growth", "core_pce_inflation"):
            mean = float(np.mean(series))
            sigma = float(np.std(series, ddof=1))
            if not np.isfinite(sigma) or sigma <= 1e-12:
                raise ValueError("Historical-mean benchmark variance invalid.")
            deterministic[:, variable_index] = mean
            draws_full[:, :, variable_index] = rng.normal(
                loc=mean,
                scale=sigma,
                size=(n_simulations, max_horizon),
            )
        else:
            innovations = np.diff(series)
            sigma = float(np.std(innovations, ddof=1))
            if not np.isfinite(sigma) or sigma <= 1e-12:
                raise ValueError("Random-walk innovation variance invalid.")
            last = float(series[-1])
            deterministic[:, variable_index] = last
            steps = rng.normal(
                loc=0.0,
                scale=sigma,
                size=(n_simulations, max_horizon),
            )
            draws_full[:, :, variable_index] = last + np.cumsum(
                steps,
                axis=1,
            )

    positions = [value - 1 for value in requested]
    return BenchmarkForecast(
        model_id=BENCHMARK_SIMPLE,
        horizons=requested,
        variables=tuple(VARIABLES),
        point=deterministic[positions, :].copy(),
        draws=draws_full[:, positions, :].copy(),
    )


def simulate_all_benchmarks(
    panel: pd.DataFrame,
    *,
    horizons: tuple[int, ...],
    simulations: int,
    seeds: dict[str, int],
) -> tuple[BenchmarkForecast, ...]:
    missing = sorted(set(BENCHMARK_IDS) - set(seeds))
    if missing:
        raise ValueError(
            "Missing benchmark seed(s): " + ", ".join(missing)
        )
    return (
        simulate_univariate_ar4(
            panel,
            horizons=horizons,
            simulations=simulations,
            seed=seeds[BENCHMARK_AR4],
        ),
        simulate_classical_var4(
            panel,
            horizons=horizons,
            simulations=simulations,
            seed=seeds[BENCHMARK_VAR4],
        ),
        simulate_historical_mean_random_walk(
            panel,
            horizons=horizons,
            simulations=simulations,
            seed=seeds[BENCHMARK_SIMPLE],
        ),
    )

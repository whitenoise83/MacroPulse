from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd
from scipy.stats import invwishart

from macropulse.bvar.model import (
    FORECAST_HORIZONS,
    VARIABLES,
    BVARPosterior,
    _panel_hash,
    _validate_panel,
)

DEFAULT_SEED = 20260904
DEFAULT_SIMULATIONS = 5000
MINIMUM_SIMULATIONS = 100
INTERVAL_COVERAGES = (0.50, 0.80, 0.95)

@dataclass(frozen=True)
class PredictiveSimulation:
    candidate_id: str
    seed: int
    simulations: int
    horizons: tuple[int, ...]
    variables: tuple[str, ...]
    estimation_last_quarter: str
    estimation_panel_hash: str
    draw_hash: str
    draws: np.ndarray
    summary: pd.DataFrame


def _validate_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise ValueError("Simulation seed must be an integer.")
    value = int(seed)
    if value < 0 or value >= 2**63:
        raise ValueError("Simulation seed must satisfy 0 <= seed < 2**63.")
    return value


def _validate_simulations(simulations: int) -> int:
    if isinstance(simulations, bool) or not isinstance(simulations, (int, np.integer)):
        raise ValueError("Simulation count must be an integer.")
    value = int(simulations)
    if value < MINIMUM_SIMULATIONS:
        raise ValueError(f"Simulation count must be at least {MINIMUM_SIMULATIONS}.")
    return value


def _validate_horizons(horizons: tuple[int, ...]) -> tuple[int, ...]:
    requested = tuple(int(value) for value in horizons)
    if not requested:
        raise ValueError("At least one forecast horizon is required.")
    if any(value <= 0 for value in requested):
        raise ValueError("Forecast horizons must be positive integers.")
    if len(set(requested)) != len(requested):
        raise ValueError("Forecast horizons must be unique.")
    if tuple(sorted(requested)) != requested:
        raise ValueError("Forecast horizons must be strictly increasing.")
    return requested


def _draw_hash(draws: np.ndarray, candidate_id: str, seed: int, horizons: tuple[int, ...], panel_hash: str) -> str:
    payload = [
        f"candidate={candidate_id}", f"seed={seed}",
        "horizons=" + ",".join(str(value) for value in horizons),
        f"panel={panel_hash}", f"shape={draws.shape}",
    ]
    digest = sha256("\n".join(payload).encode("utf-8"))
    digest.update(np.asarray(draws, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _central_interval(values: np.ndarray, coverage: float) -> tuple[np.ndarray, np.ndarray]:
    alpha = 1.0 - coverage
    return (
        np.quantile(values, alpha / 2.0, axis=0),
        np.quantile(values, 1.0 - alpha / 2.0, axis=0),
    )


def _summarise_draws(draws: np.ndarray, origin: pd.Period, horizons: tuple[int, ...]) -> pd.DataFrame:
    rows: list[dict] = []
    for horizon_position, horizon in enumerate(horizons):
        values = draws[:, horizon_position, :]
        mean = np.mean(values, axis=0)
        median = np.median(values, axis=0)
        std = np.std(values, axis=0, ddof=1)
        intervals = {coverage: _central_interval(values, coverage) for coverage in INTERVAL_COVERAGES}
        for variable_position, variable in enumerate(VARIABLES):
            row = {
                "horizon": horizon,
                "target_quarter": str(origin + horizon),
                "variable": variable,
                "mean": float(mean[variable_position]),
                "median": float(median[variable_position]),
                "std": float(std[variable_position]),
            }
            for coverage in INTERVAL_COVERAGES:
                suffix = int(round(coverage * 100))
                lower, upper = intervals[coverage]
                row[f"lower_{suffix}"] = float(lower[variable_position])
                row[f"upper_{suffix}"] = float(upper[variable_position])
            rows.append(row)
    return pd.DataFrame.from_records(rows)


def simulate_posterior_predictive(
    panel: pd.DataFrame,
    posterior: BVARPosterior,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = DEFAULT_SEED,
    horizons: tuple[int, ...] = FORECAST_HORIZONS,
) -> PredictiveSimulation:
    """Simulate the unconditional posterior predictive distribution."""
    frame = _validate_panel(panel)
    panel_hash = _panel_hash(frame)
    if panel_hash != posterior.estimation_panel_hash:
        raise ValueError("Simulation panel does not match exact posterior estimation panel.")

    n_simulations = _validate_simulations(simulations)
    simulation_seed = _validate_seed(seed)
    requested = _validate_horizons(horizons)
    if str(frame.index[-1]) != posterior.estimation_last_quarter:
        raise ValueError("Simulation panel last quarter does not match posterior origin.")

    rng = np.random.default_rng(simulation_seed)
    m = len(VARIABLES)
    k = posterior.posterior_mean.shape[0]
    max_horizon = max(requested)

    sigma_draws = invwishart.rvs(
        df=posterior.posterior_iw_df,
        scale=posterior.posterior_iw_scale,
        size=n_simulations,
        random_state=rng,
    )
    sigma_draws = np.asarray(sigma_draws, dtype=float)
    if sigma_draws.ndim == 2:
        sigma_draws = sigma_draws[None, :, :]
    if sigma_draws.shape != (n_simulations, m, m):
        raise ValueError("Unexpected inverse-Wishart draw shape.")

    coefficient_draws = np.empty((n_simulations, k, m), dtype=float)
    sigma_cholesky = np.empty((n_simulations, m, m), dtype=float)
    coefficient_cholesky = np.linalg.cholesky(posterior.posterior_covariance)

    for draw_index in range(n_simulations):
        sigma = (sigma_draws[draw_index] + sigma_draws[draw_index].T) / 2.0
        try:
            sigma_root = np.linalg.cholesky(sigma)
        except np.linalg.LinAlgError as exc:
            raise ValueError("Posterior covariance draw is not positive definite.") from exc
        sigma_cholesky[draw_index] = sigma_root
        standard_normal = rng.standard_normal((k, m))
        coefficient_draws[draw_index] = (
            posterior.posterior_mean
            + coefficient_cholesky @ standard_normal @ sigma_root.T
        )

    lags = posterior.candidate.lags
    initial_history = frame.to_numpy(dtype=float)[-lags:]
    history = np.empty((n_simulations, lags + max_horizon, m), dtype=float)
    history[:, :lags, :] = initial_history[None, :, :]
    generated = np.empty((n_simulations, max_horizon, m), dtype=float)

    for step in range(max_horizon):
        design = np.ones((n_simulations, k), dtype=float)
        offset = 1
        for lag in range(1, lags + 1):
            design[:, offset:offset + m] = history[:, lags + step - lag, :]
            offset += m
        conditional_mean = np.einsum("nk,nkm->nm", design, coefficient_draws)
        innovations = np.einsum(
            "nij,nj->ni",
            sigma_cholesky,
            rng.standard_normal((n_simulations, m)),
        )
        future = conditional_mean + innovations
        if not np.isfinite(future).all():
            raise ValueError("Posterior predictive simulation produced non-finite values.")
        generated[:, step, :] = future
        history[:, lags + step, :] = future

    selected = generated[:, [value - 1 for value in requested], :].copy()
    summary = _summarise_draws(selected, origin=frame.index[-1], horizons=requested)
    digest = _draw_hash(selected, posterior.candidate.candidate_id, simulation_seed, requested, panel_hash)

    return PredictiveSimulation(
        candidate_id=posterior.candidate.candidate_id,
        seed=simulation_seed,
        simulations=n_simulations,
        horizons=requested,
        variables=tuple(VARIABLES),
        estimation_last_quarter=posterior.estimation_last_quarter,
        estimation_panel_hash=panel_hash,
        draw_hash=digest,
        draws=selected,
        summary=summary,
    )

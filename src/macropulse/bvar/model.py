from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd


VARIABLES = (
    "real_gdp_growth",
    "core_pce_inflation",
    "unemployment_rate",
    "policy_rate",
)
LAG_CANDIDATES = (2, 4)
SHRINKAGE_CANDIDATES = (0.1, 0.2, 0.4)
FORECAST_HORIZONS = (1, 2, 4, 8)
LEVEL_VARIABLES = {"unemployment_rate", "policy_rate"}


@dataclass(frozen=True)
class BVARCandidate:
    lags: int
    shrinkage: float
    candidate_id: str


@dataclass(frozen=True)
class BVARPosterior:
    candidate: BVARCandidate
    variables: tuple[str, ...]
    observations: int
    effective_observations: int
    design_columns: int
    prior_scale: np.ndarray
    prior_mean: np.ndarray
    prior_covariance: np.ndarray
    posterior_mean: np.ndarray
    posterior_covariance: np.ndarray
    posterior_iw_scale: np.ndarray
    posterior_iw_df: float
    expected_sigma: np.ndarray
    companion_spectral_radius: float
    estimation_last_quarter: str
    estimation_panel_hash: str


def candidate_grid() -> tuple[BVARCandidate, ...]:
    candidates: list[BVARCandidate] = []
    for lags in LAG_CANDIDATES:
        for shrinkage in SHRINKAGE_CANDIDATES:
            payload = f"p={lags}|lambda={shrinkage:.6f}"
            candidate_id = sha256(payload.encode("utf-8")).hexdigest()[:16]
            candidates.append(
                BVARCandidate(
                    lags=lags,
                    shrinkage=float(shrinkage),
                    candidate_id=candidate_id,
                )
            )
    return tuple(candidates)


def _validate_candidate(candidate: BVARCandidate) -> None:
    if candidate.lags not in LAG_CANDIDATES:
        raise ValueError("Candidate lag order is outside frozen Model 2C grid.")
    if not any(
        abs(candidate.shrinkage - value) < 1e-12
        for value in SHRINKAGE_CANDIDATES
    ):
        raise ValueError("Candidate shrinkage is outside frozen Model 2C grid.")


def _validate_panel(panel: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in VARIABLES if column not in panel.columns]
    if missing:
        raise ValueError(
            "Panel missing required columns: " + ", ".join(missing)
        )

    frame = panel.loc[:, list(VARIABLES)].copy()
    if not isinstance(frame.index, pd.PeriodIndex):
        raise ValueError("BVAR panel index must be a quarterly PeriodIndex.")

    freq = str(frame.index.freqstr or "")
    if not freq.startswith("Q"):
        raise ValueError("BVAR panel index must be quarterly.")

    if frame.index.has_duplicates:
        raise ValueError("BVAR panel contains duplicate quarters.")

    frame = frame.sort_index()
    if len(frame) > 1:
        ordinals = [period.ordinal for period in frame.index]
        if any(
            current - previous != 1
            for previous, current in zip(ordinals[:-1], ordinals[1:])
        ):
            raise ValueError("BVAR panel must be contiguous by quarter.")

    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("BVAR panel contains non-finite values.")

    return frame


def _panel_hash(frame: pd.DataFrame) -> str:
    parts = ["|".join(VARIABLES)]
    for period, row in frame.iterrows():
        values = "|".join(f"{float(value):.17g}" for value in row)
        parts.append(f"{period}|{values}")
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _design(frame: pd.DataFrame, lags: int) -> tuple[np.ndarray, np.ndarray]:
    values = frame.to_numpy(dtype=float)
    design: list[list[float]] = []
    target: list[np.ndarray] = []

    for t in range(lags, len(values)):
        row = [1.0]
        for lag in range(1, lags + 1):
            row.extend(values[t - lag].tolist())
        design.append(row)
        target.append(values[t])

    return np.asarray(design, dtype=float), np.asarray(target, dtype=float)


def _sample_scales(frame: pd.DataFrame) -> np.ndarray:
    scales = frame.std(axis=0, ddof=1).to_numpy(dtype=float)
    if not np.isfinite(scales).all() or bool((scales <= 1e-10).any()):
        raise ValueError(
            "Minnesota scale requires positive finite sample standard deviations."
        )
    return scales


def _prior(
    frame: pd.DataFrame,
    lags: int,
    shrinkage: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = len(VARIABLES)
    k = 1 + m * lags
    scales = _sample_scales(frame)

    prior_mean = np.zeros((k, m), dtype=float)
    for index, variable in enumerate(VARIABLES):
        if variable in LEVEL_VARIABLES:
            prior_mean[1 + index, index] = 1.0

    prior_covariance = np.zeros((k, k), dtype=float)
    prior_covariance[0, 0] = 1_000_000.0

    for lag in range(1, lags + 1):
        for variable_index in range(m):
            row = 1 + (lag - 1) * m + variable_index
            prior_covariance[row, row] = (
                shrinkage**2
                / (lag**2 * scales[variable_index] ** 2)
            )

    return scales, prior_mean, prior_covariance


def _companion_spectral_radius(
    coefficient_mean: np.ndarray,
    lags: int,
) -> float:
    m = len(VARIABLES)
    companion = np.zeros((m * lags, m * lags), dtype=float)

    for lag_index in range(lags):
        start = 1 + lag_index * m
        stop = start + m
        companion[:m, lag_index * m : (lag_index + 1) * m] = (
            coefficient_mean[start:stop, :].T
        )

    if lags > 1:
        companion[m:, :-m] = np.eye(m * (lags - 1))

    eigenvalues = np.linalg.eigvals(companion)
    return float(np.max(np.abs(eigenvalues)))


def fit_bvar(
    panel: pd.DataFrame,
    candidate: BVARCandidate,
) -> BVARPosterior:
    _validate_candidate(candidate)
    frame = _validate_panel(panel)

    x, y = _design(frame, candidate.lags)
    if y.size == 0:
        raise ValueError("No effective observations after applying VAR lags.")

    design_columns = int(x.shape[1])
    minimum = max(24, 2 * design_columns)
    if len(y) < minimum:
        raise ValueError(
            f"Insufficient effective observations: {len(y)} < {minimum}."
        )

    scales, prior_mean, prior_covariance = _prior(
        frame,
        candidate.lags,
        candidate.shrinkage,
    )
    diagonal = np.diag(prior_covariance)
    if not np.isfinite(diagonal).all() or bool((diagonal <= 0).any()):
        raise ValueError("Prior covariance must be finite and positive.")

    prior_precision = np.diag(1.0 / diagonal)
    posterior_precision = prior_precision + x.T @ x

    try:
        posterior_covariance = np.linalg.inv(posterior_precision)
    except np.linalg.LinAlgError as exc:
        raise ValueError("Posterior coefficient covariance is singular.") from exc

    posterior_mean = posterior_covariance @ (
        prior_precision @ prior_mean + x.T @ y
    )

    m = len(VARIABLES)
    prior_iw_df = float(m + 2)
    prior_iw_scale = np.diag(scales**2)

    posterior_iw_scale = (
        prior_iw_scale
        + y.T @ y
        + prior_mean.T @ prior_precision @ prior_mean
        - posterior_mean.T @ posterior_precision @ posterior_mean
    )
    posterior_iw_scale = (
        posterior_iw_scale + posterior_iw_scale.T
    ) / 2.0

    eigenvalues = np.linalg.eigvalsh(posterior_iw_scale)
    if (
        not np.isfinite(eigenvalues).all()
        or float(eigenvalues.min()) <= 1e-10
    ):
        raise ValueError(
            "Posterior inverse-Wishart scale is not positive definite."
        )

    posterior_iw_df = prior_iw_df + len(y)
    denominator = posterior_iw_df - m - 1
    if denominator <= 0:
        raise ValueError("Posterior inverse-Wishart mean is undefined.")

    expected_sigma = posterior_iw_scale / denominator
    if not np.isfinite(expected_sigma).all():
        raise ValueError("Posterior expected covariance is non-finite.")

    return BVARPosterior(
        candidate=candidate,
        variables=tuple(VARIABLES),
        observations=len(frame),
        effective_observations=len(y),
        design_columns=design_columns,
        prior_scale=scales,
        prior_mean=prior_mean,
        prior_covariance=prior_covariance,
        posterior_mean=posterior_mean,
        posterior_covariance=posterior_covariance,
        posterior_iw_scale=posterior_iw_scale,
        posterior_iw_df=posterior_iw_df,
        expected_sigma=expected_sigma,
        companion_spectral_radius=_companion_spectral_radius(
            posterior_mean,
            candidate.lags,
        ),
        estimation_last_quarter=str(frame.index[-1]),
        estimation_panel_hash=_panel_hash(frame),
    )


def point_forecast(
    panel: pd.DataFrame,
    posterior: BVARPosterior,
    horizons: tuple[int, ...] = FORECAST_HORIZONS,
) -> pd.DataFrame:
    frame = _validate_panel(panel)

    if _panel_hash(frame) != posterior.estimation_panel_hash:
        raise ValueError(
            "Forecast panel does not match exact posterior estimation panel."
        )

    requested = tuple(int(value) for value in horizons)
    if not requested or any(value <= 0 for value in requested):
        raise ValueError("Forecast horizons must be positive integers.")

    max_horizon = max(requested)
    history = [
        row.copy()
        for row in frame.to_numpy(dtype=float)
    ]
    generated: list[np.ndarray] = []

    for _ in range(max_horizon):
        x = [1.0]
        for lag in range(1, posterior.candidate.lags + 1):
            x.extend(history[-lag].tolist())

        forecast = np.asarray(x, dtype=float) @ posterior.posterior_mean
        if not np.isfinite(forecast).all():
            raise ValueError("Posterior-mean point forecast became non-finite.")

        history.append(forecast)
        generated.append(forecast)

    origin = frame.index[-1]
    rows: list[dict] = []
    for horizon in requested:
        record = {
            "horizon": horizon,
            "target_quarter": str(origin + horizon),
        }
        for variable, value in zip(VARIABLES, generated[horizon - 1]):
            record[variable] = float(value)
        rows.append(record)

    return pd.DataFrame.from_records(rows)

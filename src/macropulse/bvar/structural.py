from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macropulse.bvar.model import VARIABLES, BVARPosterior


STRUCTURAL_ORDER = tuple(VARIABLES)
STRUCTURAL_HORIZONS = (1, 4, 8, 12)
IDENTIFICATION = "recursive_cholesky"


@dataclass(frozen=True)
class StructuralAnalysis:
    candidate_id: str
    identification: str
    ordering: tuple[str, ...]
    horizons: tuple[int, ...]
    estimation_last_quarter: str
    estimation_panel_hash: str
    impact_matrix: np.ndarray
    irf: pd.DataFrame
    fevd: pd.DataFrame


def _validate_posterior(posterior: BVARPosterior) -> None:
    if tuple(posterior.variables) != STRUCTURAL_ORDER:
        raise ValueError(
            "Posterior variable ordering does not match frozen structural ordering."
        )

    sigma = np.asarray(posterior.expected_sigma, dtype=float)
    m = len(STRUCTURAL_ORDER)
    if sigma.shape != (m, m):
        raise ValueError("Posterior expected covariance has unexpected shape.")
    if not np.isfinite(sigma).all():
        raise ValueError("Posterior expected covariance contains non-finite values.")
    if not np.allclose(sigma, sigma.T, atol=1e-10, rtol=1e-10):
        raise ValueError("Posterior expected covariance must be symmetric.")

    try:
        np.linalg.cholesky(sigma)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "Posterior expected covariance must be positive definite."
        ) from exc


def _lag_matrices(posterior: BVARPosterior) -> tuple[np.ndarray, ...]:
    m = len(STRUCTURAL_ORDER)
    matrices: list[np.ndarray] = []

    for lag_index in range(posterior.candidate.lags):
        start = 1 + lag_index * m
        stop = start + m
        block = np.asarray(
            posterior.posterior_mean[start:stop, :],
            dtype=float,
        )
        if block.shape != (m, m):
            raise ValueError("Posterior lag coefficient block has unexpected shape.")

        # Estimation stores predictors in rows and equations in columns:
        # y_t(row) = y_(t-lag)(row) @ block.
        # Structural recursions use column-vector notation, so transpose.
        matrices.append(block.T.copy())

    return tuple(matrices)


def _moving_average_matrices(
    lag_matrices: tuple[np.ndarray, ...],
    max_horizon: int,
) -> tuple[np.ndarray, ...]:
    if max_horizon < 0:
        raise ValueError("Maximum structural horizon must be non-negative.")

    m = len(STRUCTURAL_ORDER)
    psi: list[np.ndarray] = [np.eye(m, dtype=float)]

    for horizon in range(1, max_horizon + 1):
        current = np.zeros((m, m), dtype=float)
        for lag, matrix in enumerate(lag_matrices, start=1):
            if lag > horizon:
                break
            current += matrix @ psi[horizon - lag]

        if not np.isfinite(current).all():
            raise ValueError(
                "Structural moving-average recursion produced non-finite values."
            )
        psi.append(current)

    return tuple(psi)


def _irf_table(
    psi: tuple[np.ndarray, ...],
    impact: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict] = []

    for horizon in STRUCTURAL_HORIZONS:
        response_matrix = psi[horizon] @ impact

        for response_index, response in enumerate(STRUCTURAL_ORDER):
            for shock_index, shock in enumerate(STRUCTURAL_ORDER):
                rows.append(
                    {
                        "horizon": horizon,
                        "response": response,
                        "shock": shock,
                        "response_value": float(
                            response_matrix[response_index, shock_index]
                        ),
                    }
                )

    return pd.DataFrame.from_records(rows)


def _fevd_table(
    psi: tuple[np.ndarray, ...],
    impact: np.ndarray,
) -> pd.DataFrame:
    rows: list[dict] = []
    m = len(STRUCTURAL_ORDER)

    cumulative = np.zeros((m, m), dtype=float)
    requested = set(STRUCTURAL_HORIZONS)

    for step in range(max(STRUCTURAL_HORIZONS)):
        orthogonal_response = psi[step] @ impact
        cumulative += orthogonal_response**2
        horizon = step + 1

        if horizon not in requested:
            continue

        denominators = cumulative.sum(axis=1)
        if (
            not np.isfinite(denominators).all()
            or bool((denominators <= 0.0).any())
        ):
            raise ValueError("FEVD denominator is not positive and finite.")

        shares = cumulative / denominators[:, None]
        if not np.isfinite(shares).all():
            raise ValueError("FEVD produced non-finite shares.")

        tolerance = 1e-10
        if bool((shares < -tolerance).any()) or bool(
            (shares > 1.0 + tolerance).any()
        ):
            raise ValueError("FEVD shares fall outside [0, 1].")

        for response_index, response in enumerate(STRUCTURAL_ORDER):
            for shock_index, shock in enumerate(STRUCTURAL_ORDER):
                rows.append(
                    {
                        "horizon": horizon,
                        "response": response,
                        "shock": shock,
                        "share": float(shares[response_index, shock_index]),
                    }
                )

    return pd.DataFrame.from_records(rows)


def structural_analysis(posterior: BVARPosterior) -> StructuralAnalysis:
    """
    Compute point IRFs and FEVDs under the frozen recursive identification.

    Structural responses use posterior-mean VAR coefficients and the lower
    Cholesky factor of the posterior expected residual covariance. Results are
    conditional on the recursive ordering and are not unconditional causal
    claims.
    """
    _validate_posterior(posterior)

    impact = np.linalg.cholesky(
        np.asarray(posterior.expected_sigma, dtype=float)
    )
    lag_matrices = _lag_matrices(posterior)
    psi = _moving_average_matrices(
        lag_matrices,
        max(STRUCTURAL_HORIZONS),
    )

    irf = _irf_table(psi, impact)
    fevd = _fevd_table(psi, impact)

    return StructuralAnalysis(
        candidate_id=posterior.candidate.candidate_id,
        identification=IDENTIFICATION,
        ordering=STRUCTURAL_ORDER,
        horizons=STRUCTURAL_HORIZONS,
        estimation_last_quarter=posterior.estimation_last_quarter,
        estimation_panel_hash=posterior.estimation_panel_hash,
        impact_matrix=impact,
        irf=irf,
        fevd=fevd,
    )

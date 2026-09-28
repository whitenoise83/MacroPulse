from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.statespace.mlemodel import MLEModel
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Model 3D requires statsmodels>=0.14. Dependency normalization is deferred to 3I."
    ) from exc


MIN_OBSERVATIONS = 40


@dataclass(frozen=True)
class StateSpaceDiagnostics:
    converged: bool
    log_likelihood: float
    sigma_potential: float
    sigma_trend_growth: float
    sigma_gap: float
    phi1: float
    phi2: float


@dataclass(frozen=True)
class StateSpaceFit:
    estimates: pd.DataFrame
    diagnostics: StateSpaceDiagnostics
    raw_result: object


def _validate_log_gdp(y: pd.Series, minimum: int = MIN_OBSERVATIONS) -> pd.Series:
    if not isinstance(y, pd.Series):
        raise TypeError("real_gdp_log must be a pandas Series.")
    if not isinstance(y.index, pd.PeriodIndex) or not str(y.index.freqstr).startswith("Q"):
        raise ValueError("real_gdp_log must use a quarterly PeriodIndex.")
    out = y.astype(float).sort_index()
    if len(out) < minimum:
        raise ValueError(f"At least {minimum} quarterly observations are required.")
    if out.index.has_duplicates:
        raise ValueError("Quarter index contains duplicates.")
    ordinals = np.asarray([p.ordinal for p in out.index], dtype=int)
    if len(ordinals) > 1 and not np.all(np.diff(ordinals) == 1):
        raise ValueError("Quarter index must be consecutive.")
    if not np.isfinite(out.to_numpy()).all():
        raise ValueError("real_gdp_log must contain only finite values.")
    return out


def ar2_is_stationary(phi1: float, phi2: float, tol: float = 1e-10) -> bool:
    roots = np.roots([-float(phi2), -float(phi1), 1.0])
    return bool(np.all(np.abs(roots) > 1.0 + tol))


def _pacf_to_ar2(kappa1: float, kappa2: float) -> tuple[float, float]:
    phi2 = float(kappa2)
    phi1 = float(kappa1 * (1.0 - kappa2))
    return phi1, phi2


class PotentialOutputUCModel(MLEModel):
    """Identified smooth-trend UC model for log real GDP.

    States:
        0 potential_log_output
        1 trend_growth
        2 output_gap
        3 output_gap_lag1

    The direct potential-level shock is fixed at zero. Trend growth and the
    cyclical gap remain stochastic.
    """

    param_names = ["sigma_trend_growth", "sigma_gap", "phi1", "phi2"]

    def __init__(self, real_gdp_log: pd.Series):
        y = _validate_log_gdp(real_gdp_log)
        self._period_index = y.index.copy()
        observed = y.to_numpy(dtype=float)
        initial_growth = float(np.mean(np.diff(observed[: min(12, len(observed))])))
        initial_state = np.array([observed[0], initial_growth, 0.0, 0.0], dtype=float)
        initial_cov = np.diag([1e-6, 1e-4, 1e-4, 1e-4])
        super().__init__(
            endog=observed,
            k_states=4,
            k_posdef=2,
            initialization="known",
            initial_state=initial_state,
            initial_state_cov=initial_cov,
        )
        self._initial_state_anchor = initial_state
        self["design"] = np.array([[1.0, 0.0, 1.0, 0.0]])
        self["obs_cov"] = np.zeros((1, 1))
        self["selection"] = np.array(
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
                [0.0, 0.0],
            ]
        )
        self["transition"] = np.array(
            [
                [1.0, 1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.55, -0.10],
                [0.0, 0.0, 1.0, 0.0],
            ]
        )
        self["state_cov"] = np.eye(2) * 1e-4

    @property
    def start_params(self) -> np.ndarray:
        phi1, phi2 = _pacf_to_ar2(0.5, -0.1)
        return np.array([0.001, 0.01, phi1, phi2], dtype=float)

    def transform_params(self, unconstrained: np.ndarray) -> np.ndarray:
        unconstrained = np.asarray(unconstrained, dtype=float)
        constrained = unconstrained.copy()
        constrained[:2] = np.exp(np.clip(unconstrained[:2], -20.0, 5.0))
        kappa1 = np.tanh(unconstrained[2])
        kappa2 = np.tanh(unconstrained[3])
        phi1, phi2 = _pacf_to_ar2(kappa1, kappa2)
        constrained[2] = phi1
        constrained[3] = phi2
        return constrained

    def untransform_params(self, constrained: np.ndarray) -> np.ndarray:
        constrained = np.asarray(constrained, dtype=float)
        unconstrained = constrained.copy()
        if np.any(constrained[:2] <= 0.0):
            raise ValueError("Estimated state innovation standard deviations must be positive.")
        unconstrained[:2] = np.log(constrained[:2])
        phi1, phi2 = constrained[2], constrained[3]
        if not ar2_is_stationary(phi1, phi2):
            raise ValueError("AR(2) parameters are not stationary.")
        kappa2 = float(phi2)
        denom = 1.0 - kappa2
        if abs(denom) < 1e-12:
            raise ValueError("AR(2) parameters cannot be inverted safely.")
        kappa1 = float(phi1 / denom)
        eps = np.finfo(float).eps
        kappa1 = np.clip(kappa1, -1.0 + eps, 1.0 - eps)
        kappa2 = np.clip(kappa2, -1.0 + eps, 1.0 - eps)
        unconstrained[2] = np.arctanh(kappa1)
        unconstrained[3] = np.arctanh(kappa2)
        return unconstrained

    def update(self, params, transformed=True, includes_fixed=False, **kwargs):
        params = super().update(
            params, transformed=transformed, includes_fixed=includes_fixed, **kwargs
        )
        sigma_growth, sigma_gap, phi1, phi2 = params
        self["transition", 2, 2] = phi1
        self["transition", 2, 3] = phi2
        self["state_cov"] = np.diag([sigma_growth**2, sigma_gap**2])
        cov_dtype = np.result_type(phi1, phi2, sigma_gap)
        A = np.array([[phi1, phi2], [1.0, 0.0]], dtype=cov_dtype)
        Q = np.array([[sigma_gap**2, 0.0], [0.0, 0.0]], dtype=cov_dtype)
        try:
            vec_p = np.linalg.solve(np.eye(4) - np.kron(A, A), Q.reshape(4, order="F"))
            P = np.real_if_close(vec_p.reshape((2, 2), order="F"), tol=1000)
            P = np.asarray(P.real, dtype=float)
            P = 0.5 * (P + P.T)
            if np.isfinite(P).all():
                cov = np.diag([1e-6, 1e-4, 1.0, 1.0])
                cov[2:4, 2:4] = P
                self.ssm.initialize_known(self._initial_state_anchor, cov)
        except np.linalg.LinAlgError:
            pass


def _estimate_frame(index, observed, states, estimate_class):
    potential = states[0]
    growth = states[1]
    gap = observed - potential
    frame = pd.DataFrame(
        {
            "estimate_origin": index.astype(str),
            "estimate_class": estimate_class,
            "observed_log_output": observed,
            "potential_log_output": potential,
            "potential_output_level": np.exp(potential),
            "potential_output_growth_annualized_pct": 400.0 * growth,
            "output_gap_pct": 100.0 * gap,
        },
        index=index,
    )
    frame.index.name = "quarter"
    return frame


def fit_state_space(real_gdp_log: pd.Series, *, maxiter: int = 500,
                    require_convergence: bool = True) -> StateSpaceFit:
    y = _validate_log_gdp(real_gdp_log)
    model = PotentialOutputUCModel(y)
    result = model.fit(method="powell", maxiter=int(maxiter), disp=False)

    converged = bool(result.mle_retvals.get("converged", False))
    params = np.asarray(result.params, dtype=float)
    if not np.isfinite(params).all():
        raise RuntimeError("State-space estimation produced non-finite parameters.")
    if np.any(params[:2] <= 0.0):
        raise RuntimeError("State-space estimation produced non-positive standard deviations.")
    if not ar2_is_stationary(params[2], params[3]):
        raise RuntimeError("State-space estimation produced a nonstationary output-gap AR(2).")
    roots = np.roots([-float(params[3]), -float(params[2]), 1.0])
    if float(np.min(np.abs(roots))) < 1.02:
        raise RuntimeError("State-space output-gap AR(2) is too close to the unit-root boundary.")
    if params[0] / params[1] < 1e-3:
        raise RuntimeError("State-space trend-growth innovation has piled up near zero relative to the gap innovation.")
    if require_convergence and not converged:
        raise RuntimeError("State-space maximum-likelihood optimization did not converge.")

    observed = y.to_numpy(dtype=float)
    filtered = _estimate_frame(
        y.index, observed, np.asarray(result.filtered_state), "filtered_full_sample_parameters"
    )
    smoothed = _estimate_frame(
        y.index, observed, np.asarray(result.smoothed_state), "smoothed_revised"
    )

    diagnostics = StateSpaceDiagnostics(
        converged=converged,
        log_likelihood=float(result.llf),
        sigma_potential=0.0,
        sigma_trend_growth=float(params[0]),
        sigma_gap=float(params[1]),
        phi1=float(params[2]),
        phi2=float(params[3]),
    )
    return StateSpaceFit(
        estimates=pd.concat([filtered, smoothed], axis=0),
        diagnostics=diagnostics,
        raw_result=result,
    )

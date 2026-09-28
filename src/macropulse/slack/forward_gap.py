from __future__ import annotations

from dataclasses import dataclass
import hashlib
import numpy as np
import pandas as pd

GOVERNED_HORIZONS = (1, 2, 4, 8)
DENSE_PATH_HORIZONS = tuple(range(1, 9))
ESTIMATE_CLASS = (
    "forward_distribution_from_model2_gdp_uncertainty_"
    "with_deterministic_model3_potential_continuation"
)

@dataclass(frozen=True)
class Model2GDPDrawProvenance:
    model2_origin_quarter: str
    model2_candidate_id: str
    model2_draw_hash: str
    model2_estimation_panel_hash: str
    model2_seed: int
    model2_horizons: tuple[int, ...] = GOVERNED_HORIZONS

@dataclass(frozen=True)
class ForwardGapResult:
    horizons: tuple[int, ...]
    target_quarters: tuple[str, ...]
    gdp_level_draws: np.ndarray
    potential_log_path: np.ndarray
    gap_draws_pct: np.ndarray
    summary: pd.DataFrame
    provenance: Model2GDPDrawProvenance
    estimate_class: str = ESTIMATE_CLASS

def simulate_dense_model2_predictive(
    panel,
    posterior,
    *,
    n_simulations: int,
    seed: int,
):
    """Read-only dense-path adapter over the frozen Model 2 simulator."""
    from macropulse.bvar.probabilistic import simulate_posterior_predictive

    result = simulate_posterior_predictive(
        panel,
        posterior,
        n_simulations=int(n_simulations),
        seed=int(seed),
        horizons=DENSE_PATH_HORIZONS,
    )
    if tuple(result.horizons) != DENSE_PATH_HORIZONS:
        raise ValueError("Frozen Model 2 simulator did not return dense 1..8 horizons.")
    draws = np.asarray(result.draws, dtype=float)
    if draws.ndim != 3 or draws.shape[1] != len(DENSE_PATH_HORIZONS):
        raise ValueError("Dense Model 2 predictive cube has unexpected shape.")
    if not np.isfinite(draws).all():
        raise ValueError("Dense Model 2 predictive cube contains non-finite values.")
    return result

def _validate_horizons(horizons: tuple[int, ...]) -> tuple[int, ...]:
    h = tuple(int(x) for x in horizons)
    if h != GOVERNED_HORIZONS:
        raise ValueError("Model 3G requires governed Model 2 horizons (1, 2, 4, 8).")
    return h

def _validate_growth_draws(draws: np.ndarray, horizons: tuple[int, ...]) -> np.ndarray:
    x=np.asarray(draws,dtype=float)
    if x.ndim != 2 or x.shape[1] != len(horizons) or x.shape[0] < 2:
        raise ValueError("GDP growth draws must be simulation-by-horizon with at least two draws.")
    if not np.isfinite(x).all():
        raise ValueError("GDP growth draws must be finite.")
    return x

def compound_real_gdp_levels(
    gdp_growth_draws_annualized_pct: np.ndarray,
    *,
    origin_real_gdp_level: float,
    horizons: tuple[int, ...] = GOVERNED_HORIZONS,
) -> np.ndarray:
    """Compound annualised q/q log-growth draws to real-GDP levels.

    Model 2 forecasts growth at governed sparse report horizons. The predictive
    cube is generated recursively through every intermediate quarter before
    selecting horizons. A sparse cube alone therefore cannot reconstruct an
    8-quarter level path exactly. 3G fails closed rather than interpolate:
    callers must supply a dense 1..max(horizon) GDP-growth path when level
    compounding beyond adjacent reported horizons is required.
    """
    h=_validate_horizons(horizons)
    x=_validate_growth_draws(gdp_growth_draws_annualized_pct,h)
    if max(h) != len(h) or h != tuple(range(1,max(h)+1)):
        raise ValueError(
            "Sparse governed report-horizon draws cannot be compounded into "
            "GDP levels without intermediate-quarter growth draws."
        )
    if not np.isfinite(origin_real_gdp_level) or origin_real_gdp_level <= 0:
        raise ValueError("Origin real-GDP level must be finite and positive.")
    qlog=x/400.0
    return float(origin_real_gdp_level)*np.exp(np.cumsum(qlog,axis=1))

def compound_dense_real_gdp_levels(
    dense_gdp_growth_draws_annualized_pct: np.ndarray,
    *,
    origin_real_gdp_level: float,
    report_horizons: tuple[int, ...] = GOVERNED_HORIZONS,
) -> np.ndarray:
    h=_validate_horizons(report_horizons)
    x=np.asarray(dense_gdp_growth_draws_annualized_pct,dtype=float)
    if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < max(h):
        raise ValueError("Dense GDP growth draws must cover every quarter through horizon 8.")
    if not np.isfinite(x).all():
        raise ValueError("Dense GDP growth draws must be finite.")
    if not np.isfinite(origin_real_gdp_level) or origin_real_gdp_level <= 0:
        raise ValueError("Origin real-GDP level must be finite and positive.")
    dense_levels=float(origin_real_gdp_level)*np.exp(np.cumsum(x/400.0,axis=1))
    return dense_levels[:,np.asarray(h,dtype=int)-1]

def deterministic_potential_log_path(
    *,
    origin_potential_log: float,
    origin_quarterly_trend_growth: float,
    horizons: tuple[int, ...] = GOVERNED_HORIZONS,
) -> np.ndarray:
    h=_validate_horizons(horizons)
    if not np.isfinite(origin_potential_log) or not np.isfinite(origin_quarterly_trend_growth):
        raise ValueError("Model 3 origin potential state must be finite.")
    return float(origin_potential_log)+np.asarray(h,dtype=float)*float(origin_quarterly_trend_growth)

def forward_gap_distribution(
    *,
    dense_gdp_growth_draws_annualized_pct: np.ndarray,
    origin_real_gdp_level: float,
    origin_potential_log: float,
    origin_quarterly_trend_growth: float,
    origin_quarter: str,
    provenance: Model2GDPDrawProvenance,
) -> ForwardGapResult:
    h=_validate_horizons(tuple(provenance.model2_horizons))
    if str(origin_quarter) != str(provenance.model2_origin_quarter):
        raise ValueError("Model 2 and Model 3 forecast origins do not match.")
    levels=compound_dense_real_gdp_levels(
        dense_gdp_growth_draws_annualized_pct,
        origin_real_gdp_level=origin_real_gdp_level,
        report_horizons=h,
    )
    pot=deterministic_potential_log_path(
        origin_potential_log=origin_potential_log,
        origin_quarterly_trend_growth=origin_quarterly_trend_growth,
        horizons=h,
    )
    gaps=100.0*(np.log(levels)-pot[None,:])
    if not np.isfinite(gaps).all():
        raise ValueError("Forward gap distribution became non-finite.")
    origin=pd.Period(str(origin_quarter),freq="Q")
    targets=tuple(str(origin+x) for x in h)
    rows=[]
    for j,horizon in enumerate(h):
        v=gaps[:,j]
        rows.append({
            "horizon":horizon,
            "target_quarter":targets[j],
            "mean":float(np.mean(v)),
            "median":float(np.median(v)),
            "lower_80":float(np.quantile(v,0.10)),
            "upper_80":float(np.quantile(v,0.90)),
            "n_draws":int(v.size),
            "estimate_class":ESTIMATE_CLASS,
        })
    return ForwardGapResult(
        horizons=h,target_quarters=targets,gdp_level_draws=levels,
        potential_log_path=pot,gap_draws_pct=gaps,
        summary=pd.DataFrame(rows),provenance=provenance,
    )

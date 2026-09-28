from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from typing import Sequence

import numpy as np
import pandas as pd

from macropulse.slack.data import build_quarterly_panel
from macropulse.slack.state_space import fit_state_space
from macropulse.slack.vintages import canonical_snapshot_hash, information_set_id

MODEL3_SELECTED_CANDIDATE = "3D"
PRODUCTION_CURRENT_CLASS = "production_current_endpoint"
REVISED_HISTORY_CLASS = "smoothed_revised"
DENSE_MODEL2_HORIZONS = tuple(range(1, 9))
GOVERNED_REPORT_HORIZONS = (1, 2, 4, 8)


@dataclass(frozen=True)
class ProductionProvenance:
    model3_release_identity: str
    selected_candidate: str
    as_of_date: str
    information_set_id: str
    source_snapshot_hash: str
    sample_first_quarter: str
    sample_last_quarter: str
    n_observations: int
    estimate_class: str
    estimator_diagnostics: dict


@dataclass(frozen=True)
class ProductionCurrentEstimate:
    quarter: str
    observed_log_output: float
    potential_log_output: float
    potential_output_level: float
    potential_output_growth_annualized_pct: float
    output_gap_pct: float
    provenance: ProductionProvenance


def _diagnostics_dict(d) -> dict:
    return {
        "converged": bool(d.converged),
        "log_likelihood": float(d.log_likelihood),
        "sigma_potential": float(d.sigma_potential),
        "sigma_trend_growth": float(d.sigma_trend_growth),
        "sigma_gap": float(d.sigma_gap),
        "phi1": float(d.phi1),
        "phi2": float(d.phi2),
    }


def production_current_estimate(
    snapshot: pd.DataFrame,
    *,
    as_of_date: date,
    release_identity: str,
    maxiter: int = 500,
) -> ProductionCurrentEstimate:
    if not release_identity or not str(release_identity).strip():
        raise ValueError("release_identity must be non-empty.")
    panel = build_quarterly_panel(snapshot, as_of_date)
    if panel.empty:
        raise ValueError("Production information set has no complete joint quarter.")

    fit = fit_state_space(panel["real_gdp_log"], maxiter=maxiter, require_convergence=True)
    filtered = fit.estimates[
        fit.estimates["estimate_class"].eq("filtered_full_sample_parameters")
    ]
    terminal = filtered.loc[[panel.index[-1]]]
    if len(terminal) != 1:
        raise RuntimeError("Expected exactly one terminal filtered production endpoint.")
    row = terminal.iloc[0]

    snap_hash = canonical_snapshot_hash(snapshot, as_of_date)
    prov = ProductionProvenance(
        model3_release_identity=str(release_identity),
        selected_candidate=MODEL3_SELECTED_CANDIDATE,
        as_of_date=as_of_date.isoformat(),
        information_set_id=information_set_id(as_of_date, snap_hash),
        source_snapshot_hash=snap_hash,
        sample_first_quarter=str(panel.index[0]),
        sample_last_quarter=str(panel.index[-1]),
        n_observations=int(len(panel)),
        estimate_class=PRODUCTION_CURRENT_CLASS,
        estimator_diagnostics=_diagnostics_dict(fit.diagnostics),
    )
    values = np.asarray([
        row["observed_log_output"], row["potential_log_output"],
        row["potential_output_level"], row["potential_output_growth_annualized_pct"],
        row["output_gap_pct"],
    ], dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError("Production endpoint contains non-finite values.")
    return ProductionCurrentEstimate(
        quarter=str(panel.index[-1]),
        observed_log_output=float(values[0]),
        potential_log_output=float(values[1]),
        potential_output_level=float(values[2]),
        potential_output_growth_annualized_pct=float(values[3]),
        output_gap_pct=float(values[4]),
        provenance=prov,
    )


def deterministic_export_payload(result: ProductionCurrentEstimate) -> dict:
    return {
        "quarter": result.quarter,
        "observed_log_output": result.observed_log_output,
        "potential_log_output": result.potential_log_output,
        "potential_output_level": result.potential_output_level,
        "potential_output_growth_annualized_pct": result.potential_output_growth_annualized_pct,
        "output_gap_pct": result.output_gap_pct,
        "provenance": asdict(result.provenance),
    }


def deterministic_export_json(result: ProductionCurrentEstimate) -> str:
    return json.dumps(
        deterministic_export_payload(result),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"


def deterministic_export_hash(result: ProductionCurrentEstimate) -> str:
    return hashlib.sha256(deterministic_export_json(result).encode("ascii")).hexdigest()


def extract_model2_gdp_growth_draws_by_name(
    predictive_draws: np.ndarray,
    variable_names: Sequence[str],
    *,
    dense_horizons: Sequence[int] = DENSE_MODEL2_HORIZONS,
) -> np.ndarray:
    names = tuple(str(x) for x in variable_names)
    if names.count("real_gdp_growth") != 1:
        raise ValueError("Model 2 variable_names must contain real_gdp_growth exactly once.")
    x = np.asarray(predictive_draws, dtype=float)
    h = tuple(int(v) for v in dense_horizons)
    if h != DENSE_MODEL2_HORIZONS:
        raise ValueError("Production Model 3 requires dense Model 2 horizons 1..8.")
    if x.ndim != 3 or x.shape[1] != len(h) or x.shape[2] != len(names):
        raise ValueError("Predictive cube shape does not match dense horizons and variable names.")
    if not np.isfinite(x).all():
        raise ValueError("Predictive cube contains non-finite values.")
    return x[:, :, names.index("real_gdp_growth")]


def forward_gap_provenance_dimensions() -> dict:
    return {
        "dense_path_horizons": DENSE_MODEL2_HORIZONS,
        "governed_report_horizons": GOVERNED_REPORT_HORIZONS,
    }

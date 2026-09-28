from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import numpy as np
import pandas as pd

CANDIDATES = ("3D", "3E_A", "3E_B")
ESTIMATE_LABEL = "filtered_real_time_endpoint"

@dataclass(frozen=True)
class PseudoRealTimeOrigin:
    origin_id: str
    origin_quarter: str
    as_of_date: str
    information_set_hash: str

@dataclass(frozen=True)
class EndpointResult:
    origin: PseudoRealTimeOrigin
    candidate_id: str
    endpoint_gap_pct: float
    converged: bool
    admissible: bool
    diagnostics: dict
    estimate_label: str = ESTIMATE_LABEL

def validate_origins(origins: Iterable[PseudoRealTimeOrigin]) -> tuple[PseudoRealTimeOrigin, ...]:
    out=tuple(origins)
    if not out:
        raise ValueError("Pseudo-real-time origin grid is empty.")
    quarters=pd.PeriodIndex([x.origin_quarter for x in out],freq="Q")
    if quarters.has_duplicates:
        raise ValueError("Pseudo-real-time origin quarters must be unique.")
    if not quarters.is_monotonic_increasing:
        raise ValueError("Pseudo-real-time origins must be increasing.")
    if len(set(x.origin_id for x in out)) != len(out):
        raise ValueError("Pseudo-real-time origin IDs must be unique.")
    if any(not x.information_set_hash for x in out):
        raise ValueError("Every origin requires information-set provenance.")
    return out

def validate_endpoint(result: EndpointResult) -> EndpointResult:
    if result.candidate_id not in CANDIDATES:
        raise ValueError("Unknown Model 3H candidate.")
    if result.estimate_label != ESTIMATE_LABEL:
        raise ValueError("3H endpoint must use the governed real-time label.")
    if not np.isfinite(result.endpoint_gap_pct):
        raise ValueError("Endpoint gap must be finite.")
    return result

def endpoint_changes(results: pd.DataFrame) -> pd.DataFrame:
    required={"candidate_id","origin_quarter","endpoint_gap_pct"}
    if not required.issubset(results.columns):
        raise ValueError("Endpoint frame missing required columns.")
    x=results.loc[:,list(required)].copy()
    x["origin_quarter"]=pd.PeriodIndex(x["origin_quarter"],freq="Q")
    x=x.sort_values(["candidate_id","origin_quarter"])
    x["endpoint_change_pp"]=x.groupby("candidate_id")["endpoint_gap_pct"].diff()
    return x

def revision_errors(real_time: np.ndarray, revised_reference: np.ndarray) -> dict[str,float]:
    rt=np.asarray(real_time,dtype=float)
    rev=np.asarray(revised_reference,dtype=float)
    if rt.shape != rev.shape or rt.ndim != 1 or rt.size == 0:
        raise ValueError("Revision vectors must be non-empty and shape matched.")
    if not np.isfinite(rt).all() or not np.isfinite(rev).all():
        raise ValueError("Revision vectors must be finite.")
    e=rev-rt
    return {
        "mean_revision_pp":float(np.mean(e)),
        "mae_revision_pp":float(np.mean(np.abs(e))),
        "rmse_revision_pp":float(np.sqrt(np.mean(e**2))),
    }

def coverage_summary(results: pd.DataFrame) -> pd.DataFrame:
    required={"candidate_id","origin_id","converged","admissible"}
    if not required.issubset(results.columns):
        raise ValueError("Coverage frame missing required columns.")
    rows=[]
    for candidate,g in results.groupby("candidate_id",sort=True):
        n=len(g)
        rows.append({
            "candidate_id":candidate,
            "n_origins":n,
            "convergence_rate":float(g["converged"].astype(bool).mean()),
            "admissibility_rate":float(g["admissible"].astype(bool).mean()),
        })
    return pd.DataFrame(rows)

def _minimum_ar_root(phi1: float, phi2: float) -> float:
    roots=np.roots([-float(phi2),-float(phi1),1.0])
    return float(np.min(np.abs(roots)))

def _filtered_terminal(estimates: pd.DataFrame, terminal_quarter: str) -> float:
    q=pd.Period(str(terminal_quarter),freq="Q")
    x=estimates.loc[estimates["estimate_class"].eq("filtered_full_sample_parameters")]
    if q not in x.index:
        raise RuntimeError("Candidate filtered path does not contain the origin quarter.")
    value=x.loc[q,"output_gap_pct"]
    if isinstance(value,pd.Series):
        if len(value)!=1:
            raise RuntimeError("Candidate filtered endpoint is not unique.")
        value=value.iloc[0]
    value=float(value)
    if not np.isfinite(value):
        raise RuntimeError("Candidate filtered endpoint is non-finite.")
    return value

def _diagnostic_payload(diagnostics) -> dict:
    d={"log_likelihood":float(diagnostics.log_likelihood),
       "sigma_potential":float(diagnostics.sigma_potential),
       "sigma_trend_growth":float(diagnostics.sigma_trend_growth),
       "sigma_gap":float(diagnostics.sigma_gap),
       "phi1":float(diagnostics.phi1),"phi2":float(diagnostics.phi2),
       "min_ar_root_modulus":_minimum_ar_root(diagnostics.phi1,diagnostics.phi2),
       "trend_gap_sigma_ratio":float(diagnostics.sigma_trend_growth/diagnostics.sigma_gap)}
    if hasattr(diagnostics,"phillips_sign_coherent"):
        d["phillips_sign_coherent"]=diagnostics.phillips_sign_coherent
    if hasattr(diagnostics,"okun_sign_coherent"):
        d["okun_sign_coherent"]=diagnostics.okun_sign_coherent
    return d

def evaluate_snapshot_origin(snapshot: pd.DataFrame, *, as_of_date,
    expected_origin_quarter: str | None=None, maxiter_3d: int=500,
    maxiter_3e: int=1000) -> tuple[EndpointResult,...]:
    from macropulse.slack.data import build_quarterly_panel
    from macropulse.slack.vintages import canonical_snapshot_hash, information_set_id
    from macropulse.slack.state_space import fit_state_space
    from macropulse.slack.multivariate import fit_multivariate_slack
    panel=build_quarterly_panel(snapshot,as_of_date)
    if panel.empty:
        raise ValueError("Pseudo-real-time snapshot produced an empty joint panel.")
    terminal=str(panel.index[-1])
    if expected_origin_quarter is not None and terminal!=str(expected_origin_quarter):
        raise ValueError("Snapshot terminal quarter does not match the requested origin.")
    snap_hash=canonical_snapshot_hash(snapshot,as_of_date)
    origin=PseudoRealTimeOrigin(information_set_id(as_of_date,snap_hash),terminal,
        as_of_date.isoformat(),snap_hash)
    results=[]
    for candidate,cid in (("3D",None),("3E_A","3E_A"),("3E_B","3E_B")):
        try:
            fit=(fit_state_space(panel["real_gdp_log"],maxiter=maxiter_3d,
                 require_convergence=True) if candidate=="3D" else
                 fit_multivariate_slack(panel,cid,maxiter=maxiter_3e,
                 require_convergence=True))
            diag=_diagnostic_payload(fit.diagnostics)
            endpoint=_filtered_terminal(fit.estimates,terminal)
            admissible=bool(fit.diagnostics.converged and
                diag["min_ar_root_modulus"]>=1.02 and
                diag["trend_gap_sigma_ratio"]>=1e-3)
            results.append(EndpointResult(origin,candidate,endpoint,
                bool(fit.diagnostics.converged),admissible,diag))
        except Exception as exc:
            results.append(EndpointResult(origin,candidate,np.nan,False,False,
                {"failure_type":type(exc).__name__,"failure_message":str(exc)}))
    return tuple(results)

def recursive_pseudo_real_time_evaluation(inventory: pd.DataFrame, snapshot_loader,
    *, maxiter_3d: int=500, maxiter_3e: int=1000) -> pd.DataFrame:
    from macropulse.slack.vintages import validate_information_set_inventory
    validate_information_set_inventory(inventory)
    rows=[]
    use=inventory.loc[inventory["admissible_for_pseudo_real_time"].astype(bool)]
    for row in use.itertuples(index=False):
        out=evaluate_snapshot_origin(snapshot_loader(row.as_of_date),
            as_of_date=row.as_of_date,expected_origin_quarter=row.panel_last_quarter,
            maxiter_3d=maxiter_3d,maxiter_3e=maxiter_3e)
        for r in out:
            rows.append({"origin_id":r.origin.origin_id,
              "origin_quarter":r.origin.origin_quarter,"as_of_date":r.origin.as_of_date,
              "information_set_hash":r.origin.information_set_hash,
              "candidate_id":r.candidate_id,"endpoint_gap_pct":r.endpoint_gap_pct,
              "converged":r.converged,"admissible":r.admissible,
              "estimate_label":r.estimate_label,
              "failure_type":r.diagnostics.get("failure_type"),
              "diagnostics":r.diagnostics})
    return pd.DataFrame(rows)

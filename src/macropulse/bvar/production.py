from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256

import numpy as np
import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, build_complete_quarter_panel
from macropulse.bvar.model import (
    FORECAST_HORIZONS,
    BVARCandidate,
    candidate_grid,
    fit_bvar,
    point_forecast,
)
from macropulse.bvar.probabilistic import (
    DEFAULT_SEED,
    DEFAULT_SIMULATIONS,
    simulate_posterior_predictive,
)
from macropulse.bvar.structural import structural_analysis


MODEL2_VERSION = "1.0.0"
PLANNED_RELEASE_TAG = "model2-bvar-v1.0.0"

SELECTED_CANDIDATE_ID = "a69878bf644615c5"
SELECTED_LAGS = 2
SELECTED_SHRINKAGE = 0.1
SELECTION_EVIDENCE_PAYLOAD_HASH = (
    "2f65c3dda0df6d8a501887bbf34671fe80e3292b296bce3e295d9c32fff16bf7"
)

PRODUCTION_HORIZONS = tuple(FORECAST_HORIZONS)


@dataclass(frozen=True)
class Model2ForecastBundle:
    model_version: str
    planned_release_tag: str
    candidate_id: str
    lags: int
    shrinkage: float
    information_cutoff: date
    estimation_first_quarter: str
    estimation_last_quarter: str
    estimation_observations: int
    estimation_panel_hash: str
    source_snapshot_hash: str
    simulations: int
    seed: int
    companion_spectral_radius: float
    predictive_draw_hash: str
    output_fingerprint: str
    point_forecast: pd.DataFrame
    predictive_summary: pd.DataFrame
    structural_irf: pd.DataFrame
    structural_fevd: pd.DataFrame


def selected_candidate() -> BVARCandidate:
    matches = [
        candidate
        for candidate in candidate_grid()
        if candidate.candidate_id == SELECTED_CANDIDATE_ID
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Frozen Model 2 selected candidate is not uniquely present in "
            "the Model 2C candidate grid."
        )
    candidate = matches[0]
    if candidate.lags != SELECTED_LAGS:
        raise RuntimeError("Frozen Model 2 selected lag order changed.")
    if abs(candidate.shrinkage - SELECTED_SHRINKAGE) > 1e-12:
        raise RuntimeError("Frozen Model 2 selected shrinkage changed.")
    return candidate


def _normalise_cutoff(as_of_date: date) -> date:
    if isinstance(as_of_date, pd.Timestamp):
        return as_of_date.date()
    if not isinstance(as_of_date, date):
        raise ValueError("information cutoff must be a datetime.date.")
    return as_of_date


def _snapshot_hash(snapshot: pd.DataFrame, as_of_date: date) -> str:
    required = {"series_id", "observation_date", "value"}
    missing = sorted(required - set(snapshot.columns))
    if missing:
        raise ValueError(
            "Snapshot missing required columns for production hashing: "
            + ", ".join(missing)
        )

    frame = snapshot.loc[:, ["series_id", "observation_date", "value"]].copy()
    frame["series_id"] = frame["series_id"].astype(str)
    frame["observation_date"] = pd.to_datetime(
        frame["observation_date"], errors="coerce"
    )
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["series_id", "observation_date", "value"])
    frame = frame[frame["series_id"].isin(REQUIRED_SERIES)].copy()
    frame = frame.sort_values(
        ["series_id", "observation_date", "value"],
        kind="mergesort",
    )

    parts = [f"as_of={as_of_date.isoformat()}"]
    for row in frame.itertuples(index=False):
        parts.append(
            f"{row.series_id}|"
            f"{row.observation_date.date().isoformat()}|"
            f"{float(row.value):.17g}"
        )
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _frame_hash(frame: pd.DataFrame) -> str:
    parts = ["|".join(str(column) for column in frame.columns)]
    for row in frame.itertuples(index=False, name=None):
        values = []
        for value in row:
            if isinstance(value, (bool, np.bool_)):
                values.append("true" if bool(value) else "false")
            elif isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.17g}")
            elif isinstance(value, (int, np.integer)):
                values.append(str(int(value)))
            elif value is None or pd.isna(value):
                values.append("<NA>")
            else:
                values.append(str(value))
        parts.append("|".join(values))
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _output_fingerprint(
    *,
    cutoff: date,
    panel_hash: str,
    source_snapshot_hash: str,
    simulations: int,
    seed: int,
    predictive_draw_hash: str,
    point_forecast_frame: pd.DataFrame,
    predictive_summary_frame: pd.DataFrame,
    structural_irf_frame: pd.DataFrame,
    structural_fevd_frame: pd.DataFrame,
) -> str:
    parts = [
        "model2-production-v1",
        f"version={MODEL2_VERSION}",
        f"candidate={SELECTED_CANDIDATE_ID}",
        f"lags={SELECTED_LAGS}",
        f"shrinkage={SELECTED_SHRINKAGE:.6f}",
        f"cutoff={cutoff.isoformat()}",
        f"panel={panel_hash}",
        f"snapshot={source_snapshot_hash}",
        f"simulations={int(simulations)}",
        f"seed={int(seed)}",
        f"draws={predictive_draw_hash}",
        f"point={_frame_hash(point_forecast_frame)}",
        f"predictive={_frame_hash(predictive_summary_frame)}",
        f"irf={_frame_hash(structural_irf_frame)}",
        f"fevd={_frame_hash(structural_fevd_frame)}",
    ]
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def run_model2_forecast(
    snapshot: pd.DataFrame,
    as_of_date: date,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    seed: int = DEFAULT_SEED,
) -> Model2ForecastBundle:
    """
    Run the frozen Model 2 release-candidate specification.

    The public interface requires an exact-vintage snapshot plus its information
    cutoff. It performs no database writes, no candidate selection, no
    prospective adaptation, and no scenario conditioning.
    """
    cutoff = _normalise_cutoff(as_of_date)
    panel = build_complete_quarter_panel(snapshot, cutoff)
    if panel.empty:
        raise ValueError(
            "Exact-vintage snapshot does not produce a complete Model 2 panel."
        )

    candidate = selected_candidate()
    posterior = fit_bvar(panel, candidate)

    point = point_forecast(
        panel,
        posterior,
        horizons=PRODUCTION_HORIZONS,
    )
    predictive = simulate_posterior_predictive(
        panel,
        posterior,
        simulations=simulations,
        seed=seed,
        horizons=PRODUCTION_HORIZONS,
    )
    structural = structural_analysis(posterior)

    snapshot_hash = _snapshot_hash(snapshot, cutoff)
    fingerprint = _output_fingerprint(
        cutoff=cutoff,
        panel_hash=posterior.estimation_panel_hash,
        source_snapshot_hash=snapshot_hash,
        simulations=predictive.simulations,
        seed=predictive.seed,
        predictive_draw_hash=predictive.draw_hash,
        point_forecast_frame=point,
        predictive_summary_frame=predictive.summary,
        structural_irf_frame=structural.irf,
        structural_fevd_frame=structural.fevd,
    )

    return Model2ForecastBundle(
        model_version=MODEL2_VERSION,
        planned_release_tag=PLANNED_RELEASE_TAG,
        candidate_id=candidate.candidate_id,
        lags=candidate.lags,
        shrinkage=candidate.shrinkage,
        information_cutoff=cutoff,
        estimation_first_quarter=str(panel.index[0]),
        estimation_last_quarter=posterior.estimation_last_quarter,
        estimation_observations=posterior.observations,
        estimation_panel_hash=posterior.estimation_panel_hash,
        source_snapshot_hash=snapshot_hash,
        simulations=predictive.simulations,
        seed=predictive.seed,
        companion_spectral_radius=posterior.companion_spectral_radius,
        predictive_draw_hash=predictive.draw_hash,
        output_fingerprint=fingerprint,
        point_forecast=point.copy(),
        predictive_summary=predictive.summary.copy(),
        structural_irf=structural.irf.copy(),
        structural_fevd=structural.fevd.copy(),
    )

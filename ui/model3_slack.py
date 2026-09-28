from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.slack.data import REQUIRED_SERIES, build_quarterly_panel
from macropulse.slack.production import (
    MODEL3_SELECTED_CANDIDATE,
    PRODUCTION_CURRENT_CLASS,
    REVISED_HISTORY_CLASS,
    deterministic_export_hash,
    production_current_estimate,
)
from macropulse.slack.state_space import fit_state_space


ROOT = Path(__file__).resolve().parents[1]
RELEASE_CANDIDATE_PATH = ROOT / "MODEL3I_RELEASE_CANDIDATE.json"


def _planned_release_identity() -> str:
    try:
        data = json.loads(RELEASE_CANDIDATE_PATH.read_text(encoding="utf-8"))
        value = str(data["planned_release_tag"]).strip()
    except Exception as exc:
        raise RuntimeError(
            "Unable to read the governed Model 3 release-candidate identity."
        ) from exc
    if not value:
        raise RuntimeError("Model 3 planned release identity is empty.")
    return value


def _latest_complete_as_of(repository: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = f"""
    SELECT MAX(as_of_date) AS as_of_date
    FROM (
        SELECT as_of_date
        FROM snapshot_downloads
        WHERE status = 'success'
          AND series_id IN ({placeholders})
        GROUP BY as_of_date
        HAVING COUNT(DISTINCT series_id) = ?
    )
    """
    frame = repository.query_df(
        query,
        [*REQUIRED_SERIES, len(REQUIRED_SERIES)],
    )
    if frame.empty or pd.isna(frame.iloc[0]["as_of_date"]):
        return None
    return pd.Timestamp(frame.iloc[0]["as_of_date"]).date()


@st.cache_data(show_spinner=False)
def _build_model3_view(as_of_iso: str) -> dict:
    as_of_date = pd.Timestamp(as_of_iso).date()
    repository = MacroRepository()
    snapshot = repository.historical_snapshot(
        as_of_date=as_of_date,
        series_ids=list(REQUIRED_SERIES),
    )
    if snapshot.empty:
        raise RuntimeError("The selected Model 3 exact-vintage snapshot is empty.")

    release_identity = _planned_release_identity()
    current = production_current_estimate(
        snapshot,
        as_of_date=as_of_date,
        release_identity=release_identity,
    )

    panel = build_quarterly_panel(snapshot, as_of_date)
    fit = fit_state_space(
        panel["real_gdp_log"],
        maxiter=500,
        require_convergence=True,
    )
    revised = fit.estimates[
        fit.estimates["estimate_class"].eq(REVISED_HISTORY_CLASS)
    ].copy()
    if revised.empty:
        raise RuntimeError("Model 3 revised historical estimate is empty.")

    revised = revised.reset_index().rename(columns={"index": "quarter"})
    revised["quarter"] = revised["quarter"].astype(str)

    return {
        "release_identity": release_identity,
        "current": current,
        "export_hash": deterministic_export_hash(current),
        "revised": revised,
    }


st.title("Potential Output & Macroeconomic Slack — Model 3")
st.caption(
    "Governed State-Space Potential Output (3D) using exact-vintage "
    "GDP, unemployment, and Core PCE information."
)
st.info(
    "Read-only presentation layer. This page does not download data, "
    "write to the database, switch candidates, retune Model 3, or alter "
    "Models 1 or 2."
)
st.warning(
    "The current endpoint is a real-time production-class estimate from an "
    "origin-truncated information set. Historical smoothed estimates below are "
    "revised-history outputs and must not be interpreted as real-time estimates."
)

repository = MacroRepository()
if not repository.database_path.exists():
    st.error(
        "Local MacroPulse database not found. Expected: "
        f"`{repository.database_path}`"
    )
    st.stop()

try:
    as_of_date = _latest_complete_as_of(repository)
except Exception as exc:
    st.error(f"Unable to resolve the latest complete Model 3 information set: {exc}")
    st.stop()

if as_of_date is None:
    st.error(
        "No complete exact-vintage Model 3 snapshot is available for "
        + ", ".join(REQUIRED_SERIES)
        + "."
    )
    st.stop()

st.caption(
    "Latest complete exact-vintage information set: "
    f"**{as_of_date.isoformat()}** | required series: "
    + ", ".join(REQUIRED_SERIES)
)

with st.spinner("Estimating governed Model 3 current endpoint and revised history..."):
    try:
        view = _build_model3_view(as_of_date.isoformat())
    except Exception as exc:
        st.error(f"Unable to build the Model 3 view: {exc}")
        st.stop()

current = view["current"]
prov = current.provenance
diag = prov.estimator_diagnostics

cols = st.columns(4)
cols[0].metric(
    "Current output gap",
    f"{current.output_gap_pct:+.2f}%",
    help="100 × [log(actual real GDP) − log(potential real GDP)].",
)
cols[1].metric(
    "Potential growth",
    f"{current.potential_output_growth_annualized_pct:.2f}%",
    help="Annualized growth rate of the estimated potential-output path.",
)
cols[2].metric(
    "Potential GDP",
    f"{current.potential_output_level:,.1f}",
    help="Potential real GDP level in the same level units as GDPC1.",
)
cols[3].metric(
    "Current quarter",
    current.quarter,
)

if current.output_gap_pct > 0:
    st.success(
        "Current estimate indicates actual output is above estimated potential."
    )
elif current.output_gap_pct < 0:
    st.warning(
        "Current estimate indicates actual output is below estimated potential."
    )
else:
    st.info("Current estimate places actual output approximately at potential.")

st.subheader("Revised historical output gap")
revised = view["revised"].copy()
gap_chart = revised.set_index("quarter")[["output_gap_pct"]]
st.line_chart(gap_chart)
st.caption(
    f"Estimate class: `{REVISED_HISTORY_CLASS}`. "
    "This smoothed historical path uses the complete selected information set "
    "and is therefore revised history, not a pseudo-real-time sequence."
)

st.subheader("Revised potential-output path")
level_chart = revised.set_index("quarter")[
    ["potential_output_level"]
]
st.line_chart(level_chart)

st.subheader("Recent revised estimates")
recent_columns = [
    "quarter",
    "potential_output_level",
    "potential_output_growth_annualized_pct",
    "output_gap_pct",
]
recent = revised[recent_columns].tail(16).copy()
recent = recent.rename(
    columns={
        "quarter": "Quarter",
        "potential_output_level": "Potential GDP",
        "potential_output_growth_annualized_pct": "Potential growth, annualized %",
        "output_gap_pct": "Output gap %",
    }
)
st.dataframe(recent, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Governance and provenance")
gcols = st.columns(4)
gcols[0].metric("Selected candidate", prov.selected_candidate)
gcols[1].metric("Estimate class", prov.estimate_class)
gcols[2].metric("Sample observations", prov.n_observations)
gcols[3].metric(
    "Converged",
    "YES" if bool(diag.get("converged")) else "NO",
)

st.write(
    f"Release identity: `{prov.model3_release_identity}`  \n"
    f"Information set: `{prov.information_set_id}`  \n"
    f"Snapshot hash: `{prov.source_snapshot_hash}`  \n"
    f"Sample: `{prov.sample_first_quarter}` to `{prov.sample_last_quarter}`  \n"
    f"Deterministic export hash: `{view['export_hash']}`"
)

with st.expander("Estimator diagnostics"):
    st.json(diag)

st.caption(
    f"Governed production candidate: `{MODEL3_SELECTED_CANDIDATE}` | "
    f"current endpoint class: `{PRODUCTION_CURRENT_CLASS}` | "
    f"revised-history class: `{REVISED_HISTORY_CLASS}`"
)

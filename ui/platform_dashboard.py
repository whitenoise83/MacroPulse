from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.platform.dashboard import (
    change_table,
    component_table,
    due_release_table,
    forecast_table,
    model1d_dimension_table,
    model1d_prediction_table,
    provenance_table,
    snapshot_download_bytes,
    source_health_table,
    upcoming_release_table,
)
from macropulse.platform.snapshot import build_macro_snapshot


st.title("MacroPulse Platform Overview")
st.caption(
    "Read-only integrated decision-support view over the deterministic "
    "Phase 2D macro snapshot."
)
st.info(
    "This page displays persisted governed state. It does not download data, "
    "run models, create Model 1D predictions, or change promotion status."
)

as_of = st.date_input(
    "Snapshot as of",
    value=date.today(),
    max_value=date.today(),
)

repository = MacroRepository()
try:
    snapshot = build_macro_snapshot(
        repository,
        as_of=as_of,
        project_root=st.session_state.get(
            "_macropulse_project_root",
            __import__("pathlib").Path(__file__).resolve().parents[1],
        ),
    )
except Exception as exc:
    st.error(f"Unable to build the read-only platform snapshot: {exc}")
    st.stop()

readiness = snapshot.get("readiness", {})
metric_cols = st.columns(4)
metric_cols[0].metric(
    "Production sources",
    "READY" if readiness.get("production_sources_ready") else "BLOCKED",
)
metric_cols[1].metric(
    "Model 1D shadow",
    "VALID" if readiness.get("model1d_shadow_valid") else "INVALID",
)
metric_cols[2].metric(
    "Downstream platform",
    "READY" if readiness.get("platform_ready_for_downstream") else "BLOCKED",
)
metric_cols[3].metric(
    "Due releases",
    len(snapshot.get("freshness", {}).get("due_releases", []) or []),
)

st.caption(
    f"Snapshot schema {snapshot['snapshot_schema_version']} | "
    f"as of {snapshot['as_of']} | hash `{snapshot['snapshot_hash']}`"
)

st.download_button(
    "Download snapshot JSON",
    data=snapshot_download_bytes(snapshot),
    file_name=f"macro_snapshot_{as_of.strftime('%Y%m%d')}.json",
    mime="application/json",
)

st.subheader("Component readiness")
components = component_table(snapshot)
st.dataframe(
    components,
    use_container_width=True,
    hide_index=True,
)

st.subheader("Current governed forecasts")
forecasts = forecast_table(snapshot)
if forecasts.empty:
    st.warning("No governed production forecast rows are available.")
else:
    display_forecasts = forecasts.copy()
    for column in ("forecast", "lower_80", "upper_80"):
        if column in display_forecasts:
            display_forecasts[column] = pd.to_numeric(
                display_forecasts[column], errors="coerce"
            )
    st.dataframe(
        display_forecasts,
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Changes since previous governed run")
changes = change_table(snapshot)
if changes.empty:
    st.info("No previous governed run comparison is available.")
else:
    comparable = changes.loc[changes["comparable"]].copy()
    non_comparable = changes.loc[~changes["comparable"]].copy()

    if not comparable.empty:
        st.caption(
            "Forecast deltas are shown only when the current and previous "
            "governed runs refer to the same target period."
        )
        st.dataframe(
            comparable,
            use_container_width=True,
            hide_index=True,
        )

    if not non_comparable.empty:
        st.info(
            "Some changes are not directly comparable because the target period "
            "changed. They are reported as lifecycle changes rather than forecast "
            "revisions."
        )
        st.dataframe(
            non_comparable,
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("Model 1D frozen prospective shadow")
st.warning(
    "Research only. The frozen prospective observation has no production "
    "promotion, adaptive switching, blending, or replacement authority."
)

model1d = snapshot.get("model1d", {})
detail = model1d.get("status_detail") or {}
run = model1d.get("run") or {}

shadow_cols = st.columns(4)
shadow_cols[0].metric(
    "State month",
    str(run.get("state_date") or "Not available"),
)
shadow_cols[1].metric(
    "Information cutoff",
    str(run.get("information_cutoff") or "Not available"),
)
shadow_cols[2].metric(
    "Resolved outcomes",
    int(detail.get("outcome_count", 0) or 0),
)
shadow_cols[3].metric(
    "Complete target months",
    int(detail.get("complete_target_months", 0) or 0),
)

if detail.get("source_run_advance_detected"):
    st.info(
        "Newer production source runs exist, but the stored Model 1D "
        "observation remains frozen and valid."
    )

predictions = model1d_prediction_table(snapshot)
if predictions.empty:
    st.info("No frozen Model 1D prediction rows are available.")
else:
    st.markdown("#### Frozen predictions")
    prediction_columns = [
        column
        for column in (
            "benchmark_id",
            "predicted_family",
            "top1_family",
            "top1_probability",
            "top2_family",
            "top2_probability",
            "top1_top2_gap",
            "entropy",
            "probability_sum",
        )
        if column in predictions.columns
    ]
    st.dataframe(
        predictions[prediction_columns],
        use_container_width=True,
        hide_index=True,
    )

dimensions = model1d_dimension_table(snapshot)
if not dimensions.empty:
    st.markdown("#### Frozen macro dimensions")
    dimension_columns = [
        column
        for column in (
            "dimension",
            "score",
            "lower_score",
            "upper_score",
            "label",
            "confidence",
            "source_information_cutoff",
        )
        if column in dimensions.columns
    ]
    st.dataframe(
        dimensions[dimension_columns],
        use_container_width=True,
        hide_index=True,
    )
    if {"dimension", "score"}.issubset(dimensions.columns):
        chart = dimensions[["dimension", "score"]].copy()
        chart["score"] = pd.to_numeric(chart["score"], errors="coerce")
        st.bar_chart(chart.set_index("dimension"))

st.divider()
st.subheader("Freshness and release calendar")

due = due_release_table(snapshot)
if due.empty:
    st.success("No scheduled releases are due since the governed source runs.")
else:
    st.warning(f"{len(due)} scheduled release(s) are due.")
    st.dataframe(due, use_container_width=True, hide_index=True)

upcoming = upcoming_release_table(snapshot)
st.markdown("#### Upcoming releases")
if upcoming.empty:
    st.info("No upcoming release-calendar rows are available.")
else:
    st.dataframe(
        upcoming,
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Source freshness detail"):
    source_health = source_health_table(snapshot)
    if source_health.empty:
        st.info("No source-health rows are available.")
    else:
        st.dataframe(
            source_health,
            use_container_width=True,
            hide_index=True,
        )

with st.expander("Governed provenance"):
    provenance = provenance_table(snapshot)
    if provenance.empty:
        st.info("No governed provenance rows are available.")
    else:
        st.dataframe(
            provenance,
            use_container_width=True,
            hide_index=True,
        )

st.caption(
    "The dashboard is a presentation layer over the deterministic Phase 2D "
    "snapshot. Operational execution remains in Phase 2C."
)

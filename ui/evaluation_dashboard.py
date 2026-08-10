from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.dashboard import (
    comparable_revision_table,
    current_forecast_table,
    drift_table,
    evidence_flag_table,
    model1d_research_summary,
    performance_table,
    release_event_table,
    snapshot_download_bytes,
    upcoming_release_table,
)
from macropulse.evaluation.decision import (
    build_decision_intelligence_snapshot,
)


st.title("Forecast Decision Intelligence")
st.caption(
    "Read-only Phase III presentation over governed forecast evaluation, "
    "performance, revisions, freshness, and release evidence."
)
st.info(
    "This page does not download data, run models, change model selection, "
    "or mutate governed forecasts."
)

as_of = st.date_input(
    "Evidence as of",
    value=date.today(),
    max_value=date.today(),
)
root = st.session_state.get(
    "_macropulse_project_root",
    Path(__file__).resolve().parents[1],
)
repository = MacroRepository()

try:
    snapshot = build_decision_intelligence_snapshot(
        repository,
        as_of=as_of,
        project_root=root,
    )
except Exception as exc:
    st.error(f"Unable to build the read-only decision snapshot: {exc}")
    st.stop()

summary = snapshot["summary"]
cols = st.columns(5)
cols[0].metric(
    "Production sources",
    "READY" if summary["production_sources_ready"] else "BLOCKED",
)
cols[1].metric("Current targets", summary["current_target_count"])
cols[2].metric("Resolved evidence", summary["resolved_evaluation_rows"])
cols[3].metric("Comparable revisions", summary["comparable_revision_rows"])
cols[4].metric("Evidence flags", summary["evidence_flag_count"])

st.caption(
    f"Schema {snapshot['snapshot_schema_version']} | "
    f"as of {snapshot['as_of']} | hash `{snapshot['snapshot_hash']}`"
)
st.download_button(
    "Download decision snapshot JSON",
    data=snapshot_download_bytes(snapshot),
    file_name=f"decision_intelligence_{as_of.strftime('%Y%m%d')}.json",
    mime="application/json",
)

st.subheader("Current governed forecasts with evidence context")
current = current_forecast_table(snapshot)
if current.empty:
    st.warning("No current governed production forecasts are available.")
else:
    columns = [
        "component",
        "target_name",
        "target_period",
        "forecast_value",
        "lower_80",
        "upper_80",
        "recent_revision",
        "recent_revision_direction",
        "evaluation_status",
        "n_resolved_history",
        "historical_context_status",
        "mae",
        "bias",
        "interval_coverage_80",
        "drift_status",
        "freshness_state",
    ]
    st.dataframe(
        current[[column for column in columns if column in current.columns]],
        width="stretch",
        hide_index=True,
    )

st.subheader("Evidence flags")
flags = evidence_flag_table(snapshot)
if flags.empty:
    st.success("No evidence flags are active.")
else:
    st.dataframe(flags, width="stretch", hide_index=True)

st.subheader("Historical accuracy and calibration")
performance = performance_table(snapshot)
if performance.empty:
    st.info("No resolved forecast history is available yet.")
else:
    columns = [
        "component",
        "target_name",
        "n_resolved",
        "sample_status",
        "mae",
        "rmse",
        "bias",
        "interval_coverage_80",
        "directional_accuracy",
    ]
    st.dataframe(
        performance[
            [column for column in columns if column in performance.columns]
        ],
        width="stretch",
        hide_index=True,
    )

with st.expander("Drift evidence"):
    drift = drift_table(snapshot)
    if drift.empty:
        st.info("No drift evidence is available.")
    else:
        st.dataframe(drift, width="stretch", hide_index=True)

st.subheader("Recent comparable revisions")
revisions = comparable_revision_table(snapshot)
if revisions.empty:
    st.info("No same-target-period governed revisions are available.")
else:
    columns = [
        "component",
        "target_name",
        "target_period",
        "previous_information_cutoff",
        "current_information_cutoff",
        "previous_forecast_value",
        "current_forecast_value",
        "revision",
        "revision_direction",
        "associated_release_count",
        "advanced_source_release_count",
        "release_association_state",
    ]
    st.dataframe(
        revisions[
            [column for column in columns if column in revisions.columns]
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption(
        "Scheduled-release linkage is descriptive temporal association only; "
        "the dashboard does not claim causal attribution."
    )

with st.expander("Associated scheduled release events"):
    events = release_event_table(snapshot)
    if events.empty:
        st.info("No associated release events are available.")
    else:
        columns = [
            "component",
            "target_series",
            "target_period",
            "release_date",
            "series_id",
            "release_name",
            "information_set_advanced",
            "causality_claim",
        ]
        st.dataframe(
            events[[column for column in columns if column in events.columns]],
            width="stretch",
            hide_index=True,
        )

st.subheader("Upcoming governed release calendar")
upcoming = upcoming_release_table(snapshot)
if upcoming.empty:
    st.info("No upcoming release-calendar rows are available.")
else:
    st.dataframe(upcoming, width="stretch", hide_index=True)

st.divider()
st.subheader("Model 1D prospective research evidence")
st.warning(
    "Research only. Model 1D is visually and analytically separated from "
    "production forecast evaluation and has no promotion or adaptation "
    "authority here."
)
model1d = model1d_research_summary(snapshot)
if model1d.empty:
    st.info("No Model 1D research observation is available.")
else:
    st.dataframe(model1d, width="stretch", hide_index=True)

st.caption(
    "Phase 3E is a deterministic presentation layer. Phase 3B defines "
    "outcomes, Phase 3C defines performance evidence, Phase 3D defines "
    "revision/release associations, and Phase 2D defines operational state."
)

import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.service import run_macro_state
from macropulse.macro_state.versioning import current_macro_state_identity


st.title("Unified US Macro State — Model 1D")
identity = current_macro_state_identity()
st.caption(
    "Transparent aggregation of the production GDP, inflation, and labour engines"
)
st.warning(
    f"Model 1D v{identity.model_version} is a development foundation. "
    "Its thresholds and regime rules are not yet production validated."
)

repository = MacroRepository()
repository.initialise()

if st.button("Build unified macro state", type="primary"):
    with st.spinner("Selecting production source runs and scoring the macro state..."):
        try:
            result = run_macro_state(repository)
            st.success(f"Unified state completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT *
    FROM macro_state_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest.empty:
    st.info(
        "Run `python scripts\\run_macro_state.py` after successful production "
        "runs exist for Models 1A, 1B, and 1C."
    )
    st.stop()

run = latest.iloc[0]
dimensions = repository.query_df(
    """
    SELECT *
    FROM macro_state_dimensions
    WHERE run_id = ?
    ORDER BY
        CASE dimension
            WHEN 'growth' THEN 1
            WHEN 'inflation' THEN 2
            WHEN 'labour' THEN 3
            ELSE 4
        END
    """,
    [run["run_id"]],
)
inputs = repository.query_df(
    """
    SELECT *
    FROM macro_state_inputs
    WHERE run_id = ?
    ORDER BY source_model_id, source_target
    """,
    [run["run_id"]],
)
regime = repository.query_df(
    """
    SELECT *
    FROM macro_state_regimes
    WHERE run_id = ? AND is_primary = TRUE
    LIMIT 1
    """,
    [run["run_id"]],
).iloc[0]
metrics = json.loads(run["metrics_json"] or "{}")

st.subheader(str(regime["regime_label"]))
st.write(str(regime["rationale"]))

cols = st.columns(3)
for col, row in zip(cols, dimensions.itertuples(index=False)):
    delta = None if pd.isna(row.delta_score) else f"{row.delta_score:+.2f}"
    col.metric(
        row.dimension.title(),
        f"{row.score:+.2f}",
        delta=delta,
        help=(
            f"Normalized score from -2 to +2. "
            f"80% score range: {row.lower_score:+.2f} to "
            f"{row.upper_score:+.2f}."
        ),
    )
    col.caption(str(row.label))
    col.caption(f"Confidence: {row.confidence:.0f}/100")

st.metric(
    "Overall state confidence",
    f"{float(run['overall_confidence']):.0f}/100",
)
st.caption(
    f"State as of {run['state_as_of']} | source cutoff spread "
    f"{int(run['cutoff_spread_days'])} days"
)

risk_flags = metrics.get("risk_flags", [])
if risk_flags:
    st.subheader("Risk flags")
    for flag in risk_flags:
        st.warning(f"{flag['code']}: {flag['message']}")
else:
    st.success("No configured interval or synchronization risk flags.")

st.subheader("Normalized dimensions")
chart = dimensions.set_index("dimension")[["score"]]
st.bar_chart(chart)

st.subheader("Production source inputs")
st.dataframe(
    inputs[
        [
            "source_model_id",
            "source_model_version",
            "source_target_name",
            "target_period",
            "forecast_stage",
            "point_forecast",
            "lower_80",
            "upper_80",
            "information_cutoff",
        ]
    ].rename(
        columns={
            "source_model_id": "Source model",
            "source_model_version": "Version",
            "source_target_name": "Target",
            "target_period": "Target period",
            "forecast_stage": "Stage",
            "point_forecast": "Point forecast",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
            "information_cutoff": "Information cutoff",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Provenance"):
    st.write(f"Run ID: `{run['run_id']}`")
    st.write(f"GDP run ID: `{run['gdp_run_id']}`")
    st.write(f"Inflation run ID: `{run['inflation_run_id']}`")
    st.write(f"Labour run ID: `{run['labour_run_id']}`")
    st.write(f"Configuration hash: `{run['config_hash']}`")
    st.write(f"Code hash: `{run['code_hash']}`")
    st.write(f"Source bundle hash: `{run['source_bundle_hash']}`")
    st.write(f"State hash: `{run['state_hash']}`")
    st.write(f"Git commit: `{run['git_commit']}`")

st.divider()
st.header("Historical pseudo-real-time reconstruction")

history_run = repository.query_df(
    """
    SELECT *
    FROM macro_state_history_runs
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if history_run.empty:
    st.info(
        "Run `python scripts\\run_macro_state_history.py --start 2015-01-01 "
        "--end 2026-08-01` to build the first historical reconstruction."
    )
else:
    history_meta = history_run.iloc[0]
    history_states = repository.query_df(
        """
        SELECT *
        FROM macro_state_history_states
        WHERE reconstruction_id = ?
        ORDER BY state_date
        """,
        [history_meta["reconstruction_id"]],
    )
    st.caption(
        f"{history_meta['start_date']} to {history_meta['end_date']} | "
        f"{int(history_meta['months_reconstructed'])} reconstructed months | "
        f"Coverage {float(history_meta['coverage_ratio'] or 0):.1%} | "
        f"Longest contiguous run "
        f"{int(history_meta['longest_contiguous_months'] or 0)} months | "
        f"Source mode {history_meta['source_mode'] or 'legacy'} | "
        f"No-look-ahead audit: "
        f"{'pass' if history_meta['no_look_ahead_pass'] else 'fail'}"
    )

    score_chart = history_states.set_index("state_date")[
        ["growth_score", "inflation_score", "labour_score"]
    ]
    st.line_chart(score_chart)

    regime_counts = (
        history_states["primary_regime_label"]
        .value_counts()
        .rename_axis("Regime")
        .reset_index(name="Months")
    )
    st.subheader("Regime frequency")
    st.dataframe(
        regime_counts,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Latest historical states")
    st.dataframe(
        history_states[
            [
                "state_date",
                "growth_score",
                "inflation_score",
                "labour_score",
                "primary_regime_label",
                "possible_regime_count",
                "source_cutoff_spread_days",
            ]
        ].tail(24),
        use_container_width=True,
        hide_index=True,
    )

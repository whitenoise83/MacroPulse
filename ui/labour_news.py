import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.labour.news import build_labour_news_decomposition


st.title("Labour News Decomposition")
st.caption("Model 1C governed live forecast changes: new data, revisions, refit, and policy")
repository = MacroRepository()
repository.initialise()

latest = repository.query_df(
    "SELECT run_id, run_timestamp FROM labour_live_runs ORDER BY run_timestamp DESC LIMIT 1"
)
if latest.empty:
    st.info("Run the governed labour nowcast first.")
    st.stop()
run_id = str(latest.iloc[0]["run_id"])

if st.button("Rebuild latest labour news decomposition"):
    with st.spinner("Re-estimating counterfactual labour forecasts..."):
        try:
            result = build_labour_news_decomposition(repository, run_id)
            st.success(f"News status: {result['status']}")
        except Exception as exc:
            st.error(str(exc))

runs = repository.query_df(
    """
    SELECT * FROM labour_news_runs
    WHERE current_run_id = ?
    ORDER BY target_series
    """,
    [run_id],
)
if runs.empty:
    st.info("No news decomposition is stored for the latest governed run.")
    st.stop()

forecasts = repository.query_df(
    "SELECT target_series, target_name, target_unit FROM labour_live_forecasts WHERE run_id = ?",
    [run_id],
)
labels = forecasts.set_index("target_series")["target_name"].to_dict()
units = forecasts.set_index("target_series")["target_unit"].to_dict()
selected_target = st.selectbox(
    "Target", runs["target_series"].tolist(), format_func=lambda value: labels.get(value, value)
)
row = runs.loc[runs["target_series"] == selected_target].iloc[0]
unit = units.get(selected_target, "target units")
st.write(f"Status: **{row['status']}**")
if row["status"] == "success":
    col1, col2, col3 = st.columns(3)
    col1.metric("Previous forecast", f"{row['previous_forecast']:.3f}")
    col2.metric("Current forecast", f"{row['current_forecast']:.3f}")
    col3.metric("Total change", f"{row['total_change']:+.3f}")
    st.caption(f"All impacts are expressed in {unit}.")
    impacts = pd.DataFrame(
        [
            {"Channel": "New data", "Impact": row["new_data_impact"]},
            {"Channel": "Revisions/removals", "Impact": row["revision_impact"]},
            {"Channel": "Model refit", "Impact": row["model_refit_impact"]},
            {"Channel": "Stable-policy change", "Impact": row["policy_change_impact"]},
            {"Channel": "Residual interaction", "Impact": row["residual_interaction"]},
        ]
    )
    st.bar_chart(impacts.set_index("Channel"))
    st.dataframe(impacts, use_container_width=True, hide_index=True)

    contributions = repository.query_df(
        """
        SELECT contribution_type, series_id, model_name, impact, details_json
        FROM labour_news_contributions
        WHERE decomposition_id = ?
        ORDER BY contribution_type, ABS(impact) DESC
        """,
        [row["decomposition_id"]],
    )
    st.subheader("Series contributions")
    if contributions.empty:
        st.info("No changed data series were detected between the two runs.")
    else:
        st.dataframe(
            contributions.drop(columns=["details_json"]),
            use_container_width=True,
            hide_index=True,
        )

    changes = repository.query_df(
        """
        SELECT series_id, observation_date, change_type, previous_value,
               current_value, value_change
        FROM labour_release_changes
        WHERE decomposition_id = ?
        ORDER BY change_type, series_id, observation_date
        """,
        [row["decomposition_id"]],
    )
    with st.expander("Observation-level release changes"):
        st.dataframe(changes, use_container_width=True, hide_index=True)
        st.json(json.loads(row["details_json"] or "{}"))
else:
    st.info(json.loads(row["details_json"] or "{}").get("reason", row["status"]))

st.caption(f"Current governed run: {run_id}")

import json

import streamlit as st

from macropulse.data.repository import MacroRepository


st.title("Model History")

repository = MacroRepository()
repository.initialise()

runs = repository.query_df(
    '''
    SELECT run_id, run_timestamp, target_period, data_as_of, model_name, status,
           metrics_json
    FROM model_runs
    ORDER BY run_timestamp DESC
    LIMIT 100
    '''
)

if runs.empty:
    st.info("No model runs have been saved.")
    st.stop()

display_runs = runs.drop(columns=["run_id", "metrics_json"])
st.dataframe(display_runs, use_container_width=True, hide_index=True)

selected_timestamp = st.selectbox(
    "Inspect run",
    runs["run_timestamp"].astype(str).tolist(),
)

selected = runs.loc[runs["run_timestamp"].astype(str) == selected_timestamp].iloc[0]
forecasts = repository.query_df(
    '''
    SELECT model_name, point_forecast, lower_80, upper_80
    FROM forecasts
    WHERE run_id = ?
    ORDER BY model_name
    ''',
    [selected["run_id"]],
)
coefficients = repository.query_df(
    '''
    SELECT model_name, feature, coefficient
    FROM model_coefficients
    WHERE run_id = ?
    ORDER BY model_name, ABS(coefficient) DESC
    ''',
    [selected["run_id"]],
)

st.subheader("Forecasts")
st.dataframe(forecasts, use_container_width=True, hide_index=True)

st.subheader("Coefficients")
st.dataframe(coefficients, use_container_width=True, hide_index=True)

st.subheader("Run metrics")
st.json(json.loads(selected["metrics_json"]))

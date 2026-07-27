import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.services.nowcast_service import run_baseline_nowcast


st.title("US Real GDP Nowcast")
st.caption("Annualised quarter-on-quarter real GDP growth")

repository = MacroRepository()
repository.initialise()

if st.button("Run nowcast", type="primary"):
    with st.spinner("Estimating bridge, AR(1), and ensemble models..."):
        try:
            result = run_baseline_nowcast(repository)
            st.success(
                f"Completed for {result['target_period']} using data through "
                f"{result['data_as_of']}."
            )
        except Exception as exc:
            st.error(str(exc))

latest_run = repository.query_df(
    '''
    SELECT *
    FROM model_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    '''
)

if latest_run.empty:
    st.info("Run the data download and nowcast scripts first.")
    st.stop()

run = latest_run.iloc[0]
forecasts = repository.query_df(
    '''
    SELECT model_name, point_forecast, lower_80, upper_80
    FROM forecasts
    WHERE run_id = ?
    ORDER BY
        CASE model_name
            WHEN 'Equal-weight Ensemble' THEN 1
            WHEN 'Bridge Ridge' THEN 2
            ELSE 3
        END
    ''',
    [run["run_id"]],
)

ensemble = forecasts.loc[
    forecasts["model_name"] == "Equal-weight Ensemble"
].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Target quarter", run["target_period"])
col2.metric("Ensemble nowcast", f"{ensemble['point_forecast']:.2f}%")
col3.metric(
    "80% interval",
    f"{ensemble['lower_80']:.2f}% to {ensemble['upper_80']:.2f}%",
)

st.subheader("Model comparison")
chart_data = forecasts.set_index("model_name")[["point_forecast"]]
st.bar_chart(chart_data)

display = forecasts.rename(
    columns={
        "model_name": "Model",
        "point_forecast": "Forecast (%)",
        "lower_80": "Lower 80%",
        "upper_80": "Upper 80%",
    }
)
st.dataframe(display, use_container_width=True, hide_index=True)

metrics = json.loads(run["metrics_json"])
if metrics.get("imputed_features"):
    st.warning(
        "No-news carry-forward used for current-quarter features: "
        + ", ".join(metrics["imputed_features"])
    )
else:
    st.success("No current-quarter feature required carry-forward imputation.")

st.caption(
    "The interval is based on model residual dispersion. It is not yet a "
    "fully calibrated pseudo-real-time density forecast."
)

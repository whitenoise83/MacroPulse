import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.inflation.service import run_inflation_nowcast_suite


st.title("US Inflation Nowcast - Model 1B")
st.caption("Monthly annualised inflation rates | Development research model")
st.warning(
    "Model 1B v0.2.0 includes vintage-aware release-stage backtesting. Model selection, "
    "news decomposition, calibrated intervals, and production approval remain incomplete."
)
repository = MacroRepository()
repository.initialise()

if st.button("Run inflation model suite", type="primary"):
    with st.spinner("Estimating four inflation targets and baseline models..."):
        try:
            result = run_inflation_nowcast_suite(repository)
            st.success(f"Inflation nowcast run completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT * FROM inflation_model_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest.empty:
    st.info(
        "Run `python scripts\\download_inflation_data.py` and then "
        "`python scripts\\run_inflation_nowcast.py`."
    )
    st.stop()
run = latest.iloc[0]
forecasts = repository.query_df(
    """
    SELECT target_series, target_name, target_period, model_name,
           point_forecast, lower_80, upper_80
    FROM inflation_forecasts
    WHERE run_id = ?
    ORDER BY target_name, model_name
    """,
    [run["run_id"]],
)
metrics = json.loads(run["metrics_json"])
target_metrics = metrics.get("targets", {})
preferred_name = metrics.get("preferred_model", "Inflation Bridge Ridge")
preferred = forecasts.loc[forecasts["model_name"] == preferred_name].copy()

st.subheader("Headline baseline nowcasts")
columns = st.columns(4)
for column, (_, row) in zip(columns, preferred.iterrows()):
    column.metric(
        row["target_name"],
        f"{row['point_forecast']:.2f}%",
        help=f"Forecast for {row['target_period']}; monthly rate annualised.",
    )
    column.caption(f"80%: {row['lower_80']:.2f}% to {row['upper_80']:.2f}%")

selected_target = st.selectbox(
    "Target",
    preferred["target_series"].tolist(),
    format_func=lambda value: target_metrics.get(value, {}).get("target_name", value),
)
selected = forecasts.loc[forecasts["target_series"] == selected_target].copy()
selected_metrics = target_metrics.get(selected_target, {})
col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest 1m annualised", f"{selected_metrics.get('latest_monthly_annualised', float('nan')):.2f}%")
col2.metric("Latest 3m annualised", f"{selected_metrics.get('latest_three_month_annualised', float('nan')):.2f}%")
col3.metric("Latest year-over-year", f"{selected_metrics.get('latest_year_over_year', float('nan')):.2f}%")
col4.metric("Forecast month", selected_metrics.get("target_period", "—"))

st.subheader("Model comparison")
st.bar_chart(selected.set_index("model_name")[["point_forecast"]])
st.dataframe(
    selected.rename(columns={
        "model_name": "Model",
        "point_forecast": "Forecast, annualised %",
        "lower_80": "Lower 80%",
        "upper_80": "Upper 80%",
    }),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Feature freshness and technical diagnostics"):
    st.write(f"Training observations: {selected_metrics.get('training_observations', '—')}")
    st.write(f"Feature count: {selected_metrics.get('feature_count', '—')}")
    imputed = selected_metrics.get("imputed_features", [])
    if imputed:
        st.warning("Carry-forward features: " + ", ".join(imputed))
    else:
        st.success("No forecast features required carry-forward.")
    ages = selected_metrics.get("feature_ages", {})
    if ages:
        st.dataframe(
            pd.DataFrame([{"feature": key, "age_months": value} for key, value in ages.items()]),
            use_container_width=True,
            hide_index=True,
        )
    st.json(selected_metrics.get("models", {}))

st.caption(
    f"Run {run['run_id']} | Model 1B v{run['model_version']} | "
    "Research only; Model 1A GDP remains the approved production model."
)

import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.labour.service import run_labour_nowcast_suite
from macropulse.labour.versioning import current_labour_model_identity


st.title("US Labour Market Nowcast - Model 1C")
identity = current_labour_model_identity()
st.caption("Development foundation | Payrolls, unemployment and wage pressure")
st.warning(
    f"Model 1C v{identity.model_version} uses latest-revised data. "
    "It is not vintage validated or production approved."
)
repository = MacroRepository()
repository.initialise()

if st.button("Run labour nowcast", type="primary"):
    with st.spinner("Estimating labour-market models..."):
        try:
            result = run_labour_nowcast_suite(repository)
            st.success(f"Labour run completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT * FROM labour_model_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest.empty:
    st.info(
        "Run `python scripts\\download_labour_data.py`, then "
        "`python scripts\\run_labour_nowcast.py`."
    )
    st.stop()

run = latest.iloc[0]
forecasts = repository.query_df(
    """
    SELECT * FROM labour_forecasts
    WHERE run_id = ?
    ORDER BY target_name, model_name
    """,
    [run["run_id"]],
)
metrics = json.loads(run["metrics_json"] or "{}").get("targets", {})

st.subheader("Target overview")
overview_columns = st.columns(3)
for column, target_series in zip(overview_columns, forecasts["target_series"].drop_duplicates()):
    target_rows = forecasts.loc[forecasts["target_series"] == target_series]
    target_metrics = metrics.get(target_series, {})
    ensemble = target_rows.loc[
        target_rows["model_name"] == "Labour Equal-Weight Ensemble"
    ]
    headline = ensemble.iloc[0] if not ensemble.empty else target_rows.iloc[0]
    decimals = int(headline["display_decimals"])
    column.metric(
        headline["target_name"],
        f"{headline['point_forecast']:.{decimals}f}",
        help=f"Forecast for {headline['target_period']} in {headline['target_unit']}.",
    )
    column.caption(
        f"80%: {headline['lower_80']:.{decimals}f} to "
        f"{headline['upper_80']:.{decimals}f} | {headline['target_unit']}"
    )
    column.caption(
        f"Latest observed: {target_metrics.get('latest_observed_period', '—')}"
    )

selected_target = st.selectbox(
    "Target",
    forecasts["target_series"].drop_duplicates().tolist(),
    format_func=lambda value: metrics.get(value, {}).get("target_name", value),
)
selected = forecasts.loc[forecasts["target_series"] == selected_target].copy()
selected_metrics = metrics.get(selected_target, {})

col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest transformed value", f"{selected_metrics.get('latest_target_value', float('nan')):.2f}")
col2.metric("Recent 3-month mean", f"{selected_metrics.get('recent_three_month_mean', float('nan')):.2f}")
col3.metric("Latest level", f"{selected_metrics.get('latest_level', float('nan')):.2f}")
col4.metric("Forecast month", str(selected_metrics.get("target_period", "—")))

st.subheader("Model comparison")
st.bar_chart(selected.set_index("model_name")[["point_forecast"]])
st.dataframe(
    selected[
        [
            "model_name",
            "point_forecast",
            "lower_80",
            "upper_80",
            "target_unit",
        ]
    ].rename(
        columns={
            "model_name": "Model",
            "point_forecast": "Point forecast",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
            "target_unit": "Unit",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Feature freshness and diagnostics"):
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
            pd.DataFrame(
                [{"feature": key, "age_months": value} for key, value in ages.items()]
            ),
            use_container_width=True,
            hide_index=True,
        )

with st.expander("Model provenance"):
    st.write(f"Model ID: `{identity.model_id}`")
    st.write(f"Version: `{identity.model_version}`")
    st.write(f"Lifecycle: `{identity.lifecycle_status}`")
    st.write(f"Configuration hash: `{identity.config_hash}`")
    st.write(f"Code hash: `{identity.code_hash}`")
    st.write(f"Git commit: `{identity.git_commit}`")

st.caption(
    f"Run {run['run_id']} | Data as of {run['data_as_of']} | "
    "Latest-revised development output only."
)

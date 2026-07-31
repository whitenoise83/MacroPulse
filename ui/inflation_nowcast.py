import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.inflation.service import run_inflation_nowcast_suite
from macropulse.inflation.stages import INFLATION_STAGE_MAP
from macropulse.inflation.versioning import current_inflation_model_identity


st.title("US Inflation Nowcast - Model 1B")
identity = current_inflation_model_identity()
st.caption("Governed live production forecast | Monthly annualised inflation rates")
if identity.lifecycle_status == "production":
    st.success(
        f"Model 1B v{identity.model_version} is production approved. "
        "The stable target-stage policy controls headlines; the adaptive policy remains shadow-only."
    )
else:
    st.warning(
        f"Model 1B v{identity.model_version} is not production approved. "
        "The validated stable policy controls the headline; the adaptive policy is shadow-only."
    )
repository = MacroRepository()
repository.initialise()

if st.button("Run governed inflation nowcast", type="primary"):
    with st.spinner("Estimating governed CPI and PCE forecasts..."):
        try:
            result = run_inflation_nowcast_suite(repository)
            st.success(f"Governed inflation run completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT * FROM inflation_live_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest.empty:
    st.info(
        "Run `python scripts\\download_inflation_data.py`, then "
        "`python scripts\\run_inflation_nowcast.py`."
    )
    st.stop()
run = latest.iloc[0]
forecasts = repository.query_df(
    """
    SELECT * FROM inflation_live_forecasts
    WHERE run_id = ?
    ORDER BY target_name
    """,
    [run["run_id"]],
)
components = repository.query_df(
    """
    SELECT target_series, target_name, target_period, forecast_stage, model_name,
           point_forecast, raw_lower_80, raw_upper_80, role
    FROM inflation_live_components
    WHERE run_id = ?
    ORDER BY target_name, model_name
    """,
    [run["run_id"]],
)
metrics = json.loads(run["metrics_json"] or "{}")
target_metrics = metrics.get("targets", {})

st.subheader("Governed production headline" if identity.lifecycle_status == "production" else "Governed headline candidate")
columns = st.columns(4)
for column, row in zip(columns, forecasts.itertuples(index=False)):
    column.metric(
        row.target_name,
        f"{row.stable_point_forecast:.2f}%",
        help=f"{row.target_period} monthly inflation, annualised.",
    )
    column.caption(
        f"{INFLATION_STAGE_MAP[row.forecast_stage].label} | "
        f"80%: {row.lower_80:.2f}% to {row.upper_80:.2f}%"
    )

selected_target = st.selectbox(
    "Target",
    forecasts["target_series"].tolist(),
    format_func=lambda value: target_metrics.get(value, {}).get("target_name", value),
)
headline = forecasts.loc[forecasts["target_series"] == selected_target].iloc[0]
selected_components = components.loc[components["target_series"] == selected_target].copy()
selected_metrics = target_metrics.get(selected_target, {})

col1, col2, col3, col4 = st.columns(4)
col1.metric("Latest 1m annualised", f"{selected_metrics.get('latest_monthly_annualised', float('nan')):.2f}%")
col2.metric("Latest 3m annualised", f"{selected_metrics.get('latest_three_month_annualised', float('nan')):.2f}%")
col3.metric("Latest year-over-year", f"{selected_metrics.get('latest_year_over_year', float('nan')):.2f}%")
col4.metric("Forecast month", str(headline["target_period"]))

st.subheader("Policy and shadow comparison")
policy_table = pd.DataFrame(
    [
        {
            "Role": "Stable production headline" if identity.lifecycle_status == "production" else "Stable headline candidate",
            "Model": headline["stable_model_name"],
            "Forecast, annualised %": headline["stable_point_forecast"],
        },
        {
            "Role": "Adaptive shadow challenger",
            "Model": headline["shadow_model_name"],
            "Forecast, annualised %": headline["shadow_point_forecast"],
        },
    ]
)
st.dataframe(policy_table, use_container_width=True, hide_index=True)
st.caption(str(headline["shadow_selection_reason"]))

st.subheader("All model components")
st.bar_chart(selected_components.set_index("model_name")[["point_forecast"]])
st.dataframe(
    selected_components.rename(
        columns={
            "model_name": "Model",
            "point_forecast": "Forecast, annualised %",
            "raw_lower_80": "Raw lower 80%",
            "raw_upper_80": "Raw upper 80%",
            "role": "Governance role",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Governance, interval, and provenance"):
    st.write(f"Candidate validation ID: `{run['candidate_validation_id']}`")
    st.write(f"Vintage backtest ID: `{run['backtest_id']}`")
    st.write(f"Forecast stage: `{headline['forecast_stage']}`")
    st.write(f"Estimated initial release date: `{headline['estimated_release_date']}`")
    st.write(f"Interval method: `{headline['interval_method']}`")
    st.write(f"Prior errors: `{headline['interval_prior_errors']}`")
    st.write(f"Calibration cutoff month: `{headline['interval_cutoff_period']}`")
    st.write(f"Information-set hash: `{run['information_set_hash']}`")
    st.write(f"Model-state hash: `{run['model_state_hash']}`")
    st.write(f"Configuration hash: `{run['config_hash']}`")
    st.write(f"Code hash: `{run['code_hash']}`")
    st.write(f"Git commit: `{run['git_commit']}`")
    st.write(f"Governance signature: `{run['governance_signature']}`")

with st.expander("Feature freshness and target diagnostics"):
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

status_caption = (
    "Production approved; adaptive selector remains shadow-only."
    if identity.lifecycle_status == "production"
    else "Governed candidate only; not production approved."
)
st.caption(
    f"Run {run['run_id']} | Model 1B v{run['model_version']} | {status_caption}"
)

import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.labour.service import run_labour_nowcast_suite
from macropulse.labour.stages import LABOUR_STAGE_MAP
from macropulse.labour.versioning import current_labour_model_identity


st.title("US Labour Market Nowcast - Model 1C")
identity = current_labour_model_identity()
st.caption("Governed live labour forecast | Payrolls, unemployment, and wage pressure")
if identity.lifecycle_status == "production":
    st.success(
        f"Model 1C v{identity.model_version} is production approved. "
        "The stable target-stage policy controls headlines; the adaptive policy remains shadow-only."
    )
else:
    st.warning(
        f"Model 1C v{identity.model_version} is not production approved. "
        "The validated stable policy controls the headline; the adaptive policy is shadow-only."
    )
repository = MacroRepository()
repository.initialise()

if st.button("Run governed labour nowcast", type="primary"):
    with st.spinner("Estimating governed labour-market forecasts..."):
        try:
            result = run_labour_nowcast_suite(repository)
            st.success(f"Governed labour run completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT * FROM labour_live_runs
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
    SELECT * FROM labour_live_forecasts
    WHERE run_id = ?
    ORDER BY target_name
    """,
    [run["run_id"]],
)
components = repository.query_df(
    """
    SELECT target_series, target_name, target_unit, display_decimals,
           target_period, forecast_stage, model_name, point_forecast,
           raw_lower_80, raw_upper_80, role
    FROM labour_live_components
    WHERE run_id = ?
    ORDER BY target_name, model_name
    """,
    [run["run_id"]],
)
metrics = json.loads(run["metrics_json"] or "{}")
target_metrics = metrics.get("targets", {})

st.subheader(
    "Governed production headline"
    if identity.lifecycle_status == "production"
    else "Governed headline candidate"
)
columns = st.columns(3)
for column, row in zip(columns, forecasts.itertuples(index=False)):
    decimals = int(row.display_decimals)
    column.metric(
        row.target_name,
        f"{row.stable_point_forecast:.{decimals}f}",
        help=f"Forecast for {row.target_period} in {row.target_unit}.",
    )
    column.caption(
        f"{LABOUR_STAGE_MAP[row.forecast_stage].label} | "
        f"80%: {row.lower_80:.{decimals}f} to {row.upper_80:.{decimals}f}"
    )
    column.caption(row.target_unit)

selected_target = st.selectbox(
    "Target",
    forecasts["target_series"].tolist(),
    format_func=lambda value: target_metrics.get(value, {}).get("target_name", value),
)
headline = forecasts.loc[forecasts["target_series"] == selected_target].iloc[0]
selected_components = components.loc[components["target_series"] == selected_target].copy()
selected_metrics = target_metrics.get(selected_target, {})
decimals = int(headline["display_decimals"])

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Latest transformed value",
    f"{selected_metrics.get('latest_target_value', float('nan')):.{decimals}f}",
)
col2.metric(
    "Recent 3-month mean",
    f"{selected_metrics.get('recent_three_month_mean', float('nan')):.{decimals}f}",
)
col3.metric(
    "Latest level",
    f"{selected_metrics.get('latest_level', float('nan')):.{decimals}f}",
)
col4.metric("Forecast month", str(headline["target_period"]))

st.subheader("Policy and shadow comparison")
policy_table = pd.DataFrame(
    [
        {
            "Role": (
                "Stable production headline"
                if identity.lifecycle_status == "production"
                else "Stable headline candidate"
            ),
            "Model": headline["stable_model_name"],
            "Forecast": headline["stable_point_forecast"],
            "Unit": headline["target_unit"],
        },
        {
            "Role": "Adaptive shadow challenger",
            "Model": headline["shadow_model_name"],
            "Forecast": headline["shadow_point_forecast"],
            "Unit": headline["target_unit"],
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
            "point_forecast": "Forecast",
            "raw_lower_80": "Raw lower 80%",
            "raw_upper_80": "Raw upper 80%",
            "role": "Governance role",
            "target_unit": "Unit",
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
st.caption(f"Run {run['run_id']} | Model 1C v{run['model_version']} | {status_caption}")

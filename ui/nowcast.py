import json

import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.services.nowcast_service import run_model_suite_nowcast


st.title("US Real GDP Nowcast")
st.caption("Annualised quarter-on-quarter real GDP growth")

repository = MacroRepository()
repository.initialise()

if st.button("Run model suite", type="primary"):
    with st.spinner(
        "Estimating Bridge Ridge, AR(1), Dynamic Factor, and production ensembles..."
    ):
        try:
            result = run_model_suite_nowcast(repository)
            st.success(
                f"Completed for {result['target_period']} using data through "
                f"{result['data_as_of']}."
            )
            if result.get("dfm_error"):
                st.warning(
                    "The Dynamic Factor Model failed, so MacroPulse used Bridge "
                    f"Ridge as the production forecast. Reason: {result['dfm_error']}"
                )
            news = result.get("news_decomposition", {})
            if news.get("status") == "success":
                st.info(
                    "News decomposition completed. Production forecast change: "
                    f"{news.get('total_change', 0.0):+.2f} percentage points."
                )
            elif news.get("status") in {
                "no_previous_run",
                "no_previous_information_set",
            }:
                st.info(
                    "This run stored the comparison snapshot. A later run for the "
                    "same quarter will attribute incoming data and revisions."
                )
            elif news.get("status") == "failed":
                st.warning(
                    "The nowcast completed, but news attribution failed: "
                    + str(news.get("error"))
                )
        except Exception as exc:
            st.error(str(exc))

latest_run = repository.query_df(
    """
    SELECT *
    FROM model_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)

if latest_run.empty:
    st.info("Run the data download and model-suite scripts first.")
    st.stop()

run = latest_run.iloc[0]
forecasts = repository.query_df(
    """
    SELECT model_name, point_forecast, lower_80, upper_80
    FROM forecasts
    WHERE run_id = ?
    ORDER BY
        CASE model_name
            WHEN 'Stable Stage Policy' THEN 1
            WHEN 'Robust Stage-Adaptive Policy' THEN 2
            WHEN 'Rolling Bridge–DFM Ensemble' THEN 3
            WHEN 'Bridge–DFM Ensemble' THEN 4
            WHEN 'Bridge Ridge' THEN 5
            WHEN 'Dynamic Factor Model' THEN 6
            WHEN 'AR(1)' THEN 7
            ELSE 8
        END
    """,
    [run["run_id"]],
)

preferred_rows = forecasts.loc[forecasts["model_name"] == run["model_name"]]
preferred = preferred_rows.iloc[0] if not preferred_rows.empty else forecasts.iloc[0]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Target quarter", run["target_period"])
col2.metric("Preferred model", preferred["model_name"])
col3.metric("Preferred nowcast", f"{preferred['point_forecast']:.2f}%")
col4.metric(
    "80% interval",
    f"{preferred['lower_80']:.2f}% to {preferred['upper_80']:.2f}%",
)

st.subheader("Model comparison")
st.bar_chart(forecasts.set_index("model_name")[["point_forecast"]])

production_models = forecasts.loc[
    forecasts["model_name"].isin(["Bridge Ridge", "Dynamic Factor Model"])
]
model_dispersion = float(production_models["point_forecast"].std(ddof=0))
st.metric("Bridge–DFM forecast dispersion", f"{model_dispersion:.2f} pp")

st.dataframe(
    forecasts.rename(
        columns={
            "model_name": "Model",
            "point_forecast": "Forecast (%)",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

metrics = json.loads(run["metrics_json"])
identity = metrics.get("model_identity", {})
forecast_stage = metrics.get("forecast_stage")
if identity or forecast_stage:
    st.caption(
        "Governed forecast: "
        + (f"{identity.get('model_id')} v{identity.get('model_version')}" if identity else "model version unavailable")
        + (f" | stage: {forecast_stage}" if forecast_stage else "")
    )
dfm = metrics.get("dynamic_factor", {})
weights = metrics.get("production_weights", {})
weight_details = metrics.get("weight_diagnostics", {})
selection = metrics.get("production_selection", {})

if selection:
    st.caption(
        "Stable production policy: "
        + selection.get("method", "unknown").replace("_", " ")
        + (f" -> {selection.get('selected_component')}" if selection.get("selected_component") else "")
    )

if weights:
    st.subheader("Effective production weights")
    weight_cols = st.columns(len(weights))
    for column, (name, weight) in zip(weight_cols, weights.items()):
        column.metric(name, f"{weight:.1%}")
    st.caption(
        "These weights represent the component selected by the Stable Stage Policy "
        "and are the weights used by news decomposition."
    )
    rolling_candidate = metrics.get("rolling_candidate_weights", {})
    if rolling_candidate:
        with st.expander("Rolling-ensemble candidate weights"):
            st.json(
                {
                    "weights": rolling_candidate,
                    "diagnostics": weight_details,
                }
            )

if dfm.get("status") == "success":
    if dfm.get("converged"):
        st.success(
            "Dynamic Factor EM estimation converged in "
            f"{dfm.get('iterations')} iterations."
        )
    else:
        st.warning(
            "The Dynamic Factor forecast was produced, but EM did not meet the "
            "configured convergence tolerance. Review Model History diagnostics."
        )
else:
    st.warning(
        "Dynamic Factor Model unavailable for this run. Bridge Ridge is therefore "
        "the production forecast."
    )

if metrics.get("imputed_features"):
    st.warning(
        "Bridge no-news carry-forward used for: "
        + ", ".join(metrics["imputed_features"])
    )

stale_series = metrics.get("stale_series", [])
if stale_series:
    st.warning(
        "Data-freshness review required for: " + ", ".join(stale_series)
    )
with st.expander("Data freshness"):
    freshness = metrics.get("data_freshness", {})
    if freshness:
        import pandas as pd
        st.dataframe(
            pd.DataFrame.from_dict(freshness, orient="index")
            .reset_index()
            .rename(columns={"index": "series_id"}),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No freshness diagnostics were stored for this run.")

with st.expander("Dynamic Factor and policy diagnostics"):
    st.json({
        "dynamic_factor": dfm,
        "ensemble": weight_details,
        "stable_production_policy": selection,
        "robust_shadow_policy": metrics.get("robust_shadow_selection", {}),
    })

st.caption(
    "AR(1) is retained as a benchmark but receives zero production weight. "
    "The Stable Stage Policy is the production forecast; the robust adaptive policy remains a prior-only shadow challenger."
)

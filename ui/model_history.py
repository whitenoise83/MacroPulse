from __future__ import annotations

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.presentation.run_metrics import (
    dfm_rows,
    identity_rows,
    interval_rows,
    overview_rows,
    parse_metrics_json,
    selection_rows,
    shadow_selection_rows,
    weight_diagnostic_rows,
    weight_rows,
)


def _integer_display(value: object) -> str:
    try:
        if pd.isna(value):
            return "Not available"
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "Not available"


def _percentage_display(value: object) -> str:
    try:
        if pd.isna(value):
            return "Not available"
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "Not available"


st.title("Model History")
st.caption(
    "Inspect saved forecasts, model coefficients, production-weight decisions, "
    "and reproducibility diagnostics for each run."
)

repository = MacroRepository()
repository.initialise()

runs = repository.query_df(
    """
    SELECT run_id, run_timestamp, target_period, data_as_of, model_name, status,
           metrics_json
    FROM model_runs
    ORDER BY run_timestamp DESC
    LIMIT 100
    """
)

if runs.empty:
    st.info("No model runs have been saved.")
    st.stop()

run_history = runs.drop(columns=["run_id", "metrics_json"]).rename(
    columns={
        "run_timestamp": "Run time",
        "target_period": "Target quarter",
        "data_as_of": "Data as of",
        "model_name": "Headline model",
        "status": "Status",
    }
)
st.subheader("Recent runs")
st.dataframe(run_history, use_container_width=True, hide_index=True)

runs = runs.copy()
runs["_run_label"] = runs.apply(
    lambda row: (
        f"{row['run_timestamp']} | {row['target_period']} | "
        f"{row['model_name']} | {str(row['run_id'])[:8]}"
    ),
    axis=1,
)
selected_label = st.selectbox("Inspect run", runs["_run_label"].tolist())
selected = runs.loc[runs["_run_label"] == selected_label].iloc[0]
metrics = parse_metrics_json(selected.get("metrics_json"))

forecasts = repository.query_df(
    """
    SELECT model_name, point_forecast, lower_80, upper_80
    FROM forecasts
    WHERE run_id = ?
    ORDER BY model_name
    """,
    [selected["run_id"]],
)
coefficients = repository.query_df(
    """
    SELECT model_name, feature, coefficient
    FROM model_coefficients
    WHERE run_id = ?
    ORDER BY model_name, ABS(coefficient) DESC
    """,
    [selected["run_id"]],
)

st.divider()
st.subheader(f"Selected run: {selected['target_period']}")
st.caption(
    f"Run ID: {selected['run_id']} | Run time: {selected['run_timestamp']} | "
    f"Data as of: {selected['data_as_of']}"
)

card_1, card_2, card_3, card_4 = st.columns(4)
card_1.metric(
    "Production policy",
    str(metrics.get("preferred_model") or selected["model_name"]),
)
card_2.metric(
    "Training observations",
    _integer_display(metrics.get("training_observations")),
)
card_3.metric(
    "Indicators used",
    _integer_display(metrics.get("feature_count")),
)
interval = metrics.get("interval")
card_4.metric(
    "Target forecast interval",
    _percentage_display(interval),
)

st.subheader("Forecasts")
if forecasts.empty:
    st.info("No forecasts were stored for this run.")
else:
    forecast_display = forecasts.rename(
        columns={
            "model_name": "Model",
            "point_forecast": "Forecast (%)",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
        }
    )
    st.dataframe(
        forecast_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Forecast (%)": st.column_config.NumberColumn(format="%.2f"),
            "Lower 80%": st.column_config.NumberColumn(format="%.2f"),
            "Upper 80%": st.column_config.NumberColumn(format="%.2f"),
        },
    )

st.subheader("Run metrics")
overview = overview_rows(metrics)
if overview:
    st.dataframe(pd.DataFrame(overview), use_container_width=True, hide_index=True)
else:
    st.info("No structured run metrics were stored for this run.")

weights = weight_rows(metrics)
if weights:
    st.markdown("#### Effective production weights")
    weight_columns = st.columns(len(weights))
    for column, row in zip(weight_columns, weights):
        column.metric(row["Model"], row["Weight display"])

    weight_details = weight_diagnostic_rows(metrics)
    if weight_details:
        st.dataframe(
            pd.DataFrame(weight_details),
            use_container_width=True,
            hide_index=True,
        )

selection = selection_rows(metrics)
if selection:
    st.markdown("#### Stable production component")
    st.dataframe(pd.DataFrame(selection), use_container_width=True, hide_index=True)

shadow_selection = shadow_selection_rows(metrics)
if shadow_selection:
    st.markdown("#### Robust adaptive shadow challenger")
    st.dataframe(pd.DataFrame(shadow_selection), use_container_width=True, hide_index=True)

model_diagnostics = dfm_rows(metrics)
if model_diagnostics:
    st.markdown("#### Dynamic Factor Model diagnostics")
    dfm_status = str(metrics.get("dynamic_factor", {}).get("status", "")).lower()
    converged = metrics.get("dynamic_factor", {}).get("converged")
    if dfm_status == "failed":
        st.warning("The Dynamic Factor Model failed for this run; inspect the error below.")
    elif converged is False:
        st.warning("A DFM forecast was produced, but EM convergence was not achieved.")
    elif converged is True:
        st.success("Dynamic Factor EM estimation converged.")
    st.dataframe(
        pd.DataFrame(model_diagnostics),
        use_container_width=True,
        hide_index=True,
    )

calibration = interval_rows(metrics)
if calibration:
    with st.expander("Interval calibration"):
        st.dataframe(
            pd.DataFrame(calibration),
            use_container_width=True,
            hide_index=True,
        )

identity = identity_rows(metrics)
if identity:
    with st.expander("Reproducibility and model identity"):
        st.dataframe(pd.DataFrame(identity), use_container_width=True, hide_index=True)

st.subheader("Coefficients")
if coefficients.empty:
    st.info("No coefficients were stored for this run or selected model suite.")
else:
    coefficient_display = coefficients.rename(
        columns={
            "model_name": "Model",
            "feature": "Feature",
            "coefficient": "Coefficient",
        }
    )
    st.dataframe(
        coefficient_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Coefficient": st.column_config.NumberColumn(format="%.4f"),
        },
    )

with st.expander("Advanced technical details — raw JSON"):
    st.caption(
        "This machine-readable payload is retained for audit and debugging. "
        "The formatted sections above are the normal user-facing view."
    )
    if metrics:
        st.json(metrics)
    else:
        st.code(str(selected.get("metrics_json") or "No raw metrics payload."))

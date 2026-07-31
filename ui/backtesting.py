import json

import pandas as pd
import streamlit as st

from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    calculate_regime_metrics,
)
from macropulse.data.repository import MacroRepository


st.title("Pseudo-real-time Backtesting")
st.caption(
    "Quarter-end GDP nowcasts estimated only with observations and revisions "
    "available on each historical forecast date."
)

repository = MacroRepository()
repository.initialise()

runs = repository.query_df(
    """
    SELECT backtest_id, created_at, start_date, end_date, status, metrics_json,
           skipped_json, notes
    FROM backtest_runs
    ORDER BY created_at DESC
    LIMIT 50
    """
)

if runs.empty:
    st.info(
        "No backtest has been saved. Run `python scripts\\run_backtest.py "
        "--start 2015-03-31` in CMD, then refresh this page."
    )
    st.stop()

run_labels = {
    row["backtest_id"]: (
        f"{row['created_at']} | {row['start_date']} to {row['end_date']} | "
        f"{row['status']}"
    )
    for _, row in runs.iterrows()
}
selected_id = st.selectbox(
    "Backtest run",
    options=list(run_labels),
    format_func=lambda value: run_labels[value],
)
selected_run = runs.loc[runs["backtest_id"] == selected_id].iloc[0]

results = repository.query_df(
    """
    SELECT forecast_date, target_period, actual_release_date, model_name,
           point_forecast, actual, error, abs_error, squared_error,
           lower_80, upper_80, direction_correct, interval_covered,
           imputed_feature_count
    FROM backtest_results
    WHERE backtest_id = ?
    ORDER BY forecast_date, model_name
    """,
    [selected_id],
)

diagnostics = repository.query_df(
    """
    SELECT forecast_date, target_period, model_name, status, converged,
           iterations, convergence_criterion, log_likelihood, details_json
    FROM backtest_diagnostics
    WHERE backtest_id = ?
    ORDER BY forecast_date, model_name
    """,
    [selected_id],
)

notices = json.loads(selected_run["skipped_json"] or "[]")
pending = [item for item in notices if item.get("scope") == "pending_outcome"]
issues = [item for item in notices if item.get("scope") != "pending_outcome"]

if results.empty:
    st.warning("This run contains no successful forecast rows.")
    if notices:
        st.dataframe(pd.DataFrame(notices), use_container_width=True, hide_index=True)
    st.stop()

metrics = calculate_backtest_metrics(results)
regime_metrics = calculate_regime_metrics(results)

best_rmse = metrics.sort_values("rmse").iloc[0]
best_mae = metrics.sort_values("mae").iloc[0]
base_rate = float(metrics["positive_base_rate_accuracy"].iloc[0])
col1, col2, col3, col4 = st.columns(4)
col1.metric("Lowest RMSE", best_rmse["model_name"])
col2.metric("RMSE", f"{best_rmse['rmse']:.2f}")
col3.metric("Lowest MAE", best_mae["model_name"])
col4.metric("Always-positive accuracy", f"{base_rate:.1%}")

st.subheader("Full-sample model comparison")
metrics_display = metrics.copy()
for column in [
    "rmse",
    "trimmed_rmse_10",
    "mae",
    "median_ae",
    "max_abs_error",
    "bias",
]:
    metrics_display[column] = metrics_display[column].round(2)
for column in [
    "direction_accuracy",
    "positive_base_rate_accuracy",
    "direction_skill",
    "interval_coverage",
    "win_rate",
]:
    metrics_display[column] = (metrics_display[column] * 100).round(1)
st.dataframe(metrics_display, use_container_width=True, hide_index=True)

if metrics["observations"].nunique() > 1:
    st.warning(
        "Model sample sizes differ. Review convergence and compare common quarters "
        "before treating small ranking differences as decisive."
    )

st.subheader("Regime and recent-sample performance")
sample = st.selectbox("Sample", regime_metrics["sample"].unique())
regime_display = regime_metrics.loc[regime_metrics["sample"] == sample].copy()
for column in ["rmse", "trimmed_rmse_10", "mae", "median_ae", "bias"]:
    regime_display[column] = regime_display[column].round(2)
for column in ["direction_accuracy", "direction_skill", "interval_coverage", "win_rate"]:
    regime_display[column] = (regime_display[column] * 100).round(1)
st.dataframe(regime_display, use_container_width=True, hide_index=True)

st.subheader("Forecasts versus initial GDP outcome")
chart_data = results.pivot_table(
    index="forecast_date",
    columns="model_name",
    values="point_forecast",
    aggfunc="first",
)
actual = results.groupby("forecast_date")["actual"].first().rename("Actual")
chart_data = chart_data.join(actual).sort_index()
st.line_chart(chart_data, use_container_width=True)

st.subheader("Cumulative squared-error difference versus Bridge Ridge")
squared = results.pivot_table(
    index="forecast_date",
    columns="model_name",
    values="squared_error",
    aggfunc="first",
).sort_index()
if "Bridge Ridge" in squared.columns:
    relative = squared.subtract(squared["Bridge Ridge"], axis=0).drop(
        columns=["Bridge Ridge"], errors="ignore"
    )
    st.line_chart(relative.cumsum(), use_container_width=True)
    st.caption(
        "A falling or negative line indicates cumulative improvement over Bridge Ridge."
    )

st.subheader("Absolute forecast errors")
error_chart = results.pivot_table(
    index="forecast_date",
    columns="model_name",
    values="abs_error",
    aggfunc="first",
).sort_index()
st.bar_chart(error_chart, use_container_width=True)

if not diagnostics.empty:
    dfm_diagnostics = diagnostics.loc[
        diagnostics["model_name"] == "Dynamic Factor Model"
    ].copy()
    if not dfm_diagnostics.empty:
        successful = dfm_diagnostics["status"] == "success"
        converged = dfm_diagnostics["converged"].fillna(False)
        c1, c2, c3 = st.columns(3)
        c1.metric("DFM attempted quarters", len(dfm_diagnostics))
        c2.metric("DFM successful fits", int(successful.sum()))
        c3.metric("EM convergence rate", f"{100 * converged.mean():.1f}%")
        with st.expander("Dynamic Factor convergence details"):
            display_diag = dfm_diagnostics.drop(columns=["details_json"]).copy()
            display_diag["convergence_criterion"] = display_diag[
                "convergence_criterion"
            ].round(6)
            display_diag["log_likelihood"] = display_diag["log_likelihood"].round(2)
            st.dataframe(display_diag, use_container_width=True, hide_index=True)

    weight_diagnostics = diagnostics.loc[
        diagnostics["model_name"] == "Rolling Bridge–DFM Ensemble"
    ].copy()
    if not weight_diagnostics.empty:
        weight_rows = []
        for _, row in weight_diagnostics.iterrows():
            details = json.loads(row["details_json"] or "{}")
            weights = details.get("weights", {})
            weight_rows.append(
                {
                    "forecast_date": row["forecast_date"],
                    "target_period": row["target_period"],
                    "method": details.get("weight_method"),
                    "history_quarters": details.get("common_history"),
                    "Bridge Ridge": weights.get("Bridge Ridge", 0.5),
                    "Dynamic Factor Model": weights.get(
                        "Dynamic Factor Model", 0.5
                    ),
                }
            )
        weights_frame = pd.DataFrame(weight_rows).set_index("forecast_date")
        st.subheader("Rolling production weights")
        st.line_chart(
            weights_frame[["Bridge Ridge", "Dynamic Factor Model"]],
            use_container_width=True,
        )
        with st.expander("Weight history"):
            st.dataframe(weights_frame.reset_index(), use_container_width=True, hide_index=True)

st.subheader("Period-level results")
model_filter = st.multiselect(
    "Models",
    options=sorted(results["model_name"].unique()),
    default=sorted(results["model_name"].unique()),
)
display = results.loc[results["model_name"].isin(model_filter)].copy()
for column in ["point_forecast", "actual", "error", "abs_error", "lower_80", "upper_80"]:
    display[column] = display[column].round(2)
st.dataframe(display, use_container_width=True, hide_index=True)

if pending:
    with st.expander(f"Pending outcomes ({len(pending)})", expanded=True):
        st.dataframe(pd.DataFrame(pending), use_container_width=True, hide_index=True)
if issues:
    with st.expander(f"Skipped quarters and model failures ({len(issues)})"):
        st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

with st.expander("Methodology note"):
    st.write(selected_run["notes"])
    st.markdown(
        "Rolling ensemble weights are calculated from prior common Bridge and DFM "
        "errors only. The current quarter's realised GDP value never influences its "
        "own weight. Direction skill is reported relative to an always-positive rule."
    )

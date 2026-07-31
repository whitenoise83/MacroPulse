import pandas as pd
import streamlit as st

from macropulse.backtesting.metrics import (
    calculate_backtest_metrics,
    calculate_regime_metrics,
)
from macropulse.data.repository import MacroRepository


st.title("Model Comparison")
st.caption("Compare live nowcasts with robust pseudo-real-time performance.")

repository = MacroRepository()
repository.initialise()

latest_run = repository.query_df(
    """
    SELECT run_id, run_timestamp, target_period, model_name
    FROM model_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest_run.empty:
    st.info("No live model run is available.")
else:
    run = latest_run.iloc[0]
    live = repository.query_df(
        """
        SELECT model_name, point_forecast, lower_80, upper_80
        FROM forecasts
        WHERE run_id = ?
        ORDER BY model_name
        """,
        [run["run_id"]],
    )
    st.subheader(f"Latest nowcast: {run['target_period']}")
    st.dataframe(live.round(3), use_container_width=True, hide_index=True)
    st.bar_chart(live.set_index("model_name")[["point_forecast"]])

latest_backtest = repository.query_df(
    """
    SELECT backtest_id, created_at, start_date, end_date, status
    FROM backtest_runs
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if latest_backtest.empty:
    st.info("Run a current backtest to compare historical performance.")
    st.stop()

backtest = latest_backtest.iloc[0]
results = repository.query_df(
    """
    SELECT forecast_date, target_period, model_name, point_forecast, actual,
           lower_80, upper_80
    FROM backtest_results
    WHERE backtest_id = ?
    """,
    [backtest["backtest_id"]],
)
metrics = calculate_backtest_metrics(results)
regimes = calculate_regime_metrics(results)

st.subheader(f"Latest backtest: {backtest['start_date']} to {backtest['end_date']}")
if metrics.empty:
    st.warning("The latest backtest has no successful model forecasts.")
else:
    display = metrics.copy()
    for column in [
        "rmse",
        "trimmed_rmse_10",
        "mae",
        "median_ae",
        "max_abs_error",
        "bias",
    ]:
        display[column] = display[column].round(3)
    for column in [
        "direction_accuracy",
        "positive_base_rate_accuracy",
        "direction_skill",
        "interval_coverage",
        "win_rate",
    ]:
        display[column] = (display[column] * 100).round(1)
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.bar_chart(metrics.set_index("model_name")[["rmse", "mae", "median_ae"]])

    if not regimes.empty:
        sample = st.selectbox("Performance sample", regimes["sample"].unique())
        regime_display = regimes.loc[regimes["sample"] == sample].copy()
        for column in ["rmse", "trimmed_rmse_10", "mae", "median_ae", "bias"]:
            regime_display[column] = regime_display[column].round(3)
        st.dataframe(regime_display, use_container_width=True, hide_index=True)

    common_counts = results.groupby("model_name").size().rename("quarters")
    if common_counts.nunique() > 1:
        st.warning(
            "Models have different evaluation counts. Compare common quarters "
            "before treating the ranking as decisive."
        )

st.caption(
    "Direction skill is measured relative to an always-positive GDP-growth rule. "
    "AR(1) remains a benchmark and is excluded from production ensemble weights."
)

import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.labour.backtest import run_chronological_labour_backtest


st.title("Labour Backtesting - Model 1C")
repository = MacroRepository()
repository.initialise()

vintage_tab, revised_tab = st.tabs([
    "Vintage release-stage backtest",
    "Latest-revised baseline",
])

with vintage_tab:
    st.caption("Pseudo-real-time ALFRED evidence using initial-release labour outcomes")
    latest_vintage = repository.query_df(
        """
        SELECT * FROM labour_vintage_backtest_runs
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if latest_vintage.empty:
        st.info(
            "Run `python scripts\\download_labour_initial_targets.py`, then "
            "`python scripts\\run_labour_vintage_backtest.py --start 2016-01`."
        )
    else:
        run = latest_vintage.iloc[0]
        results = repository.query_df(
            """
            SELECT * FROM labour_vintage_backtest_results
            WHERE backtest_id = ?
            ORDER BY target_series, forecast_stage, target_period, model_name
            """,
            [run["backtest_id"]],
        )
        st.caption(
            f"Backtest {run['backtest_id']} | Status: {run['status']} | "
            f"Model version: {run['model_version']}"
        )
        if not results.empty:
            target = st.selectbox(
                "Vintage target",
                sorted(results["target_series"].unique().tolist()),
                key="labour_vintage_target",
            )
            stages = sorted(
                results.loc[results["target_series"] == target, "forecast_stage"].unique().tolist()
            )
            stage = st.selectbox("Forecast stage", stages, key="labour_vintage_stage")
            chosen = results.loc[
                (results["target_series"] == target)
                & (results["forecast_stage"] == stage)
            ].copy()
            metric_rows = []
            for model, frame in chosen.groupby("model_name"):
                error = pd.to_numeric(frame["error"], errors="coerce").dropna()
                metric_rows.append({
                    "model_name": model,
                    "observations": len(error),
                    "rmse": float((error.pow(2).mean()) ** 0.5),
                    "mae": float(error.abs().mean()),
                    "bias": float(error.mean()),
                    "p90_abs_error": float(error.abs().quantile(0.90)),
                    "max_abs_error": float(error.abs().max()),
                    "directional_accuracy": float(frame["direction_correct"].mean()),
                    "interval_coverage": float(frame["interval_covered"].mean()),
                })
            metrics = pd.DataFrame(metric_rows).sort_values(["rmse", "mae"])
            st.subheader("Pseudo-real-time model metrics")
            st.dataframe(metrics, use_container_width=True, hide_index=True)
            selected_model = st.selectbox(
                "Vintage model",
                metrics["model_name"].tolist(),
                key="labour_vintage_model",
            )
            history = chosen.loc[chosen["model_name"] == selected_model].copy()
            history["target_period"] = pd.to_datetime(history["target_period"])
            st.line_chart(history.set_index("target_period")[["actual", "point_forecast"]])
            st.dataframe(
                history[[
                    "target_period", "forecast_date", "actual_release_date",
                    "actual", "point_forecast", "error", "regime",
                    "direction_correct", "interval_covered",
                ]].tail(48),
                use_container_width=True,
                hide_index=True,
            )
        latest_validation = repository.query_df(
            """
            SELECT * FROM labour_validation_runs
            WHERE backtest_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [run["backtest_id"]],
        )
        if not latest_validation.empty:
            validation = latest_validation.iloc[0]
            st.subheader("Latest vintage validation")
            st.write({
                "status": validation["status"],
                "passed": int(validation["passed_gates"]),
                "failed": int(validation["failed_gates"]),
                "warnings": int(validation["warning_gates"]),
                "report": validation["report_path"],
            })

with revised_tab:
    st.caption("Latest-revised chronological engineering benchmark")
    st.warning(
        "These results are not pseudo-real-time. They use today's revised data and "
        "full-month feature values. Pandemic observations strongly influence RMSE and maximum error."
    )
    start_period = st.text_input("First evaluated month", value="2016-01")
    if st.button("Run labour baseline backtest", type="primary"):
        with st.spinner("Running chronological labour backtest..."):
            try:
                result = run_chronological_labour_backtest(repository, start_period)
                st.success(f"Backtest completed: {result['backtest_id']}")
            except Exception as exc:
                st.error(str(exc))

    latest = repository.query_df(
        """
        SELECT * FROM labour_backtest_runs
        WHERE status = 'success'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if latest.empty:
        st.info("Run `python scripts\\run_labour_backtest.py --start 2016-01`.")
    else:
        run = latest.iloc[0]
        results = repository.query_df(
            """
            SELECT * FROM labour_backtest_results
            WHERE backtest_id = ?
            ORDER BY target_series, target_period, model_name
            """,
            [run["backtest_id"]],
        )
        summary = json.loads(run["metrics_json"] or "{}")
        rows: list[dict] = []
        for target, models in summary.items():
            for model, metrics in models.items():
                rows.append({"target_series": target, "model_name": model, **metrics})
        metrics_frame = pd.DataFrame(rows)
        if not metrics_frame.empty:
            selected_target = st.selectbox(
                "Baseline target",
                sorted(metrics_frame["target_series"].unique().tolist()),
            )
            selected_metrics = metrics_frame.loc[
                metrics_frame["target_series"] == selected_target
            ].sort_values(["rmse", "mae"])
            st.subheader("Model metrics")
            st.dataframe(selected_metrics, use_container_width=True, hide_index=True)
            st.subheader("Forecast history")
            history = results.loc[results["target_series"] == selected_target].copy()
            model = st.selectbox("Baseline model", sorted(history["model_name"].unique().tolist()))
            model_history = history.loc[history["model_name"] == model].copy()
            model_history["target_period"] = pd.to_datetime(model_history["target_period"])
            st.line_chart(model_history.set_index("target_period")[["actual", "point_forecast"]])

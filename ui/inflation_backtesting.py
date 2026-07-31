import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository


st.title("Inflation Backtesting")
st.caption("Model 1B development evidence: pseudo-real-time vintages and revised-data benchmarks")
repository = MacroRepository()
repository.initialise()

vintage_tab, baseline_tab = st.tabs(
    ["Vintage release-stage backtest", "Latest-revised baseline"]
)

with vintage_tab:
    st.info(
        "This is the preferred validation view. Forecasts use historical ALFRED "
        "information sets and are evaluated against each target's initial-release snapshot."
    )
    latest = repository.query_df(
        """
        SELECT * FROM inflation_vintage_backtest_runs
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if latest.empty:
        st.warning(
            "Run `python scripts\\download_inflation_initial_targets.py` and then "
            "`python scripts\\run_inflation_vintage_backtest.py --start 2015-01`."
        )
    else:
        run = latest.iloc[0]
        results = repository.query_df(
            """
            SELECT * FROM inflation_vintage_backtest_results
            WHERE backtest_id = ?
            ORDER BY target_series, forecast_stage, target_period, model_name
            """,
            [run["backtest_id"]],
        )
        if results.empty:
            st.warning("The latest vintage backtest contains no stored forecasts.")
        else:
            calibration_run = repository.query_df(
                """
                SELECT * FROM inflation_interval_calibration_runs
                WHERE backtest_id = ? AND status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [run["backtest_id"]],
            )
            calibrated = pd.DataFrame()
            if not calibration_run.empty:
                calibration_id = calibration_run.iloc[0]["calibration_id"]
                calibrated = repository.query_df(
                    """
                    SELECT target_series, forecast_stage, target_period, model_name,
                           interval_covered AS calibrated_interval_covered,
                           interval_half_width, prior_error_count,
                           calibration_status
                    FROM inflation_interval_calibrated_results
                    WHERE calibration_id = ?
                    """,
                    [calibration_id],
                )
                results = results.merge(
                    calibrated,
                    on=["target_series", "forecast_stage", "target_period", "model_name"],
                    how="left",
                )
                st.success(
                    "Coverage uses prior-only rolling forecast-error calibration. "
                    f"Calibration ID: {calibration_id}"
                )
            else:
                st.warning(
                    "Coverage still uses in-sample residual intervals. Run "
                    "`python scripts/calibrate_inflation_intervals.py`."
                )

            target = st.selectbox(
                "Inflation target",
                sorted(results["target_series"].unique()),
                key="inflation_vintage_target",
            )
            target_rows = results.loc[results["target_series"] == target].copy()
            stage = st.selectbox(
                "Forecast stage",
                sorted(target_rows["forecast_stage"].unique()),
                key="inflation_vintage_stage",
            )
            selected = target_rows.loc[target_rows["forecast_stage"] == stage].copy()
            metrics_rows = []
            for model_name, frame in selected.groupby("model_name"):
                error = pd.to_numeric(frame["error"], errors="coerce")
                metrics_rows.append(
                    {
                        "Model": model_name,
                        "Observations": int(len(frame)),
                        "RMSE": float((error.pow(2).mean()) ** 0.5),
                        "MAE": float(error.abs().mean()),
                        "Bias": float(error.mean()),
                        "Median AE": float(error.abs().median()),
                        "Coverage": float(
                            frame[
                                "calibrated_interval_covered"
                                if "calibrated_interval_covered" in frame.columns
                                else "interval_covered"
                            ].mean()
                        ),
                    }
                )
            metrics = pd.DataFrame(metrics_rows).sort_values("RMSE")
            champion = metrics.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Lowest vintage RMSE", f"{champion['RMSE']:.2f}")
            c2.metric("Leading model", champion["Model"])
            c3.metric("Evaluated months", int(champion["Observations"]))
            c4.metric("80% coverage", f"{champion['Coverage']:.1%}")
            display = metrics.copy()
            display["RMSE"] = display["RMSE"].map(lambda value: f"{value:.2f}")
            display["MAE"] = display["MAE"].map(lambda value: f"{value:.2f}")
            display["Bias"] = display["Bias"].map(lambda value: f"{value:.2f}")
            display["Median AE"] = display["Median AE"].map(lambda value: f"{value:.2f}")
            display["Coverage"] = display["Coverage"].map(lambda value: f"{value:.1%}")
            st.dataframe(display, use_container_width=True, hide_index=True)

            history = selected[
                ["target_period", "model_name", "point_forecast", "actual"]
            ].copy()
            pivot = history.pivot(
                index="target_period", columns="model_name", values="point_forecast"
            )
            actual = history.drop_duplicates("target_period").set_index("target_period")[["actual"]]
            st.subheader("Pseudo-real-time forecast history")
            st.line_chart(actual.join(pivot))

            validation = repository.query_df(
                """
                SELECT * FROM inflation_validation_runs
                WHERE backtest_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [run["backtest_id"]],
            )
            if not validation.empty:
                val = validation.iloc[0]
                st.subheader("Latest vintage validation")
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("Status", str(val["status"]).upper())
                v2.metric("Passed", int(val["passed_checks"]))
                v3.metric("Failed", int(val["failed_checks"]))
                v4.metric("Warnings", int(val["warnings"]))
                st.caption(f"Report: {val['report_path']}")

            notices = json.loads(run["notices_json"] or "[]")
            pending = [item for item in notices if item.get("kind") == "pending"]
            warmup = [
                item
                for item in notices
                if item.get("kind") == "warmup"
                or "complete training months are available" in item.get("message", "")
            ]
            issues = [
                item
                for item in notices
                if item not in pending and item not in warmup
            ]
            if pending:
                st.caption(f"Pending unreleased target months: {len(pending)}")
            if warmup:
                st.caption(
                    f"Expected training-history warm-up skips: {len(warmup)}"
                )
            if issues:
                with st.expander(f"Backtest issues ({len(issues)})"):
                    st.json(issues)
            st.caption(
                f"Method: pseudo-real-time ALFRED release stages | "
                f"Backtest ID: {run['backtest_id']}"
            )

with baseline_tab:
    st.warning(
        "This tab uses latest revised data. It remains useful as an engineering "
        "benchmark but is not the formal Model 1B validation evidence."
    )
    latest = repository.query_df(
        """
        SELECT * FROM inflation_backtest_runs
        WHERE status = 'success'
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    if latest.empty:
        st.info("Run `python scripts\\run_inflation_backtest.py --start 2015-01`.")
    else:
        run = latest.iloc[0]
        metrics = json.loads(run["metrics_json"])
        rows = []
        for target, models in metrics.items():
            for model, values in models.items():
                rows.append({"target_series": target, "model_name": model, **values})
        summary = pd.DataFrame(rows)
        if summary.empty:
            st.info("No baseline metrics were stored.")
        else:
            selected = st.selectbox(
                "Target",
                sorted(summary["target_series"].unique()),
                key="inflation_baseline_target",
            )
            target_summary = summary.loc[
                summary["target_series"] == selected
            ].sort_values("rmse")
            champion = target_summary.iloc[0]
            col1, col2, col3 = st.columns(3)
            col1.metric("Lowest baseline RMSE", f"{champion['rmse']:.2f}")
            col2.metric("Model", champion["model_name"])
            col3.metric("Observations", int(champion["observations"]))
            st.dataframe(target_summary, use_container_width=True, hide_index=True)
            results = repository.query_df(
                """
                SELECT target_period, model_name, point_forecast, actual, abs_error
                FROM inflation_backtest_results
                WHERE backtest_id = ? AND target_series = ?
                ORDER BY target_period, model_name
                """,
                [run["backtest_id"], selected],
            )
            if not results.empty:
                pivot = results.pivot(
                    index="target_period", columns="model_name", values="point_forecast"
                )
                actual = results.drop_duplicates("target_period").set_index("target_period")[["actual"]]
                st.subheader("Forecast history")
                st.line_chart(actual.join(pivot))
            st.caption(f"Method: {run['method']} | Backtest ID: {run['backtest_id']}")

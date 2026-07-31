import json

import pandas as pd
import streamlit as st

from macropulse.backtesting.metrics import (
    calculate_stage_metrics,
    calculate_stage_regime_metrics,
)
from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
)
from macropulse.data.repository import MacroRepository
from macropulse.governance.versioning import load_governance_config


st.title("Model Validation & Governance")
st.caption(
    "Model 1A v1.0.0 production evidence: approved Stable Stage Policy, robust adaptive "
    "shadow challenger, interval quality, regime robustness, reproducibility, and governance."
)

repository = MacroRepository()
repository.initialise()
governance = load_governance_config()
champion = str(governance.get("model", {}).get("champion_model", STABLE_STAGE_POLICY_NAME))

model_registry = repository.query_df(
    """
    SELECT model_id, model_version, display_name, lifecycle_status, config_hash,
           code_hash, git_commit, registered_at
    FROM model_registry
    ORDER BY registered_at DESC
    LIMIT 20
    """
)

if model_registry.empty:
    st.warning("No model version is registered. Run `python scripts\\initialise_database.py`.")
else:
    latest_model = model_registry.iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Model", latest_model["model_id"])
    c2.metric("Version", latest_model["model_version"])
    c3.metric("Lifecycle", latest_model["lifecycle_status"])
    with st.expander("Reproducibility signature"):
        st.code(
            f"config_hash={latest_model['config_hash']}\n"
            f"code_hash={latest_model['code_hash']}\n"
            f"git_commit={latest_model['git_commit']}"
        )


    approval_rows = repository.query_df(
        """
        SELECT promoted_version, source_model_version, validation_id, decision,
               approved_at, freeze_assessment_report, recorded_at
        FROM model_approvals
        WHERE model_id = ?
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        [latest_model["model_id"]],
    )
    if not approval_rows.empty:
        approval = approval_rows.iloc[0]
        st.success(
            f"Production approval recorded: v{approval['promoted_version']} | "
            f"validation {approval['validation_id']} | {approval['approved_at']}"
        )
        with st.expander("Production approval record"):
            st.dataframe(approval_rows, use_container_width=True, hide_index=True)

stage_runs = repository.query_df(
    """
    SELECT stage_backtest_id, created_at, model_version, start_date, end_date, status,
           config_json, notices_json, notes
    FROM stage_backtest_runs
    ORDER BY created_at DESC
    LIMIT 30
    """
)

if stage_runs.empty:
    st.info(
        "No staged backtest exists. Run `python scripts\\run_staged_backtest.py "
        "--start 2015-01-01` and refresh this page."
    )
else:
    labels = {
        row["stage_backtest_id"]: (
            f"{row['created_at']} | v{row['model_version']} | "
            f"{row['start_date']} to {row['end_date']} | {row['status']}"
        )
        for _, row in stage_runs.iterrows()
    }
    selected_stage_id = st.selectbox(
        "Staged backtest run",
        options=list(labels),
        format_func=lambda value: labels[value],
    )
    stage_results = repository.query_df(
        """
        SELECT *
        FROM stage_backtest_results
        WHERE stage_backtest_id = ?
        ORDER BY forecast_date, forecast_stage, model_name
        """,
        [selected_stage_id],
    )
    stage_diagnostics = repository.query_df(
        """
        SELECT *
        FROM stage_backtest_diagnostics
        WHERE stage_backtest_id = ?
        ORDER BY forecast_date, forecast_stage, model_name
        """,
        [selected_stage_id],
    )

    if not stage_results.empty:
        metrics = calculate_stage_metrics(stage_results)
        champion_metrics = metrics.loc[metrics["model_name"] == champion].copy()
        if champion_metrics.empty:
            st.warning(
                f"This older run does not contain `{champion}`. Use the approved v0.6.1 staged validation history."
            )
        else:
            st.subheader("Stable production policy through the quarter")
            chart = champion_metrics.set_index("forecast_stage")[["rmse", "mae"]]
            st.line_chart(chart, use_container_width=True)
            display = champion_metrics[
                [
                    "forecast_stage",
                    "observations",
                    "rmse",
                    "mae",
                    "median_ae",
                    "bias",
                    "interval_coverage",
                    "average_interval_width",
                    "interval_score_80",
                    "coverage_p_value",
                    "average_days_to_release",
                ]
            ].copy()
            for column in [
                "rmse",
                "mae",
                "median_ae",
                "bias",
                "average_interval_width",
                "interval_score_80",
                "average_days_to_release",
            ]:
                display[column] = display[column].round(2)
            display["interval_coverage"] = (display["interval_coverage"] * 100).round(1)
            display["coverage_p_value"] = display["coverage_p_value"].round(3)
            st.dataframe(display, use_container_width=True, hide_index=True)

        if not stage_diagnostics.empty:
            stable = stage_diagnostics.loc[
                stage_diagnostics["model_name"] == STABLE_STAGE_POLICY_NAME
            ].copy()
            if not stable.empty:
                stable["selected_component"] = stable["details_json"].map(
                    lambda value: json.loads(value or "{}").get("selected_component", "Unknown")
                )
                stable_distribution = (
                    stable.groupby(["forecast_stage", "selected_component"])
                    .size()
                    .rename("forecasts")
                    .reset_index()
                )
                st.subheader("Stable production components")
                st.dataframe(stable_distribution, use_container_width=True, hide_index=True)

            selections = stage_diagnostics.loc[
                stage_diagnostics["model_name"] == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
            ].copy()
            if not selections.empty:
                parsed = selections["details_json"].map(lambda value: json.loads(value or "{}"))
                selections["selected_component"] = parsed.map(
                    lambda item: item.get("selected_component", "Unknown")
                )
                selections["selection_method"] = parsed.map(
                    lambda item: item.get("method", "Unknown")
                )
                selections["switched"] = parsed.map(lambda item: bool(item.get("switched", False)))
                distribution = (
                    selections.groupby(
                        ["forecast_stage", "selected_component", "selection_method"]
                    )
                    .size()
                    .rename("forecasts")
                    .reset_index()
                )
                st.subheader("Robust adaptive shadow selections")
                st.dataframe(distribution, use_container_width=True, hide_index=True)
                stability_rows = []
                for stage, group in selections.groupby("forecast_stage", sort=False):
                    chosen = group.sort_values("forecast_date")["selected_component"].astype(str).tolist()
                    switches = sum(left != right for left, right in zip(chosen, chosen[1:]))
                    stability_rows.append({
                        "forecast_stage": stage,
                        "forecasts": len(chosen),
                        "switches": switches,
                        "switch_rate": switches / max(len(chosen) - 1, 1),
                    })
                stability = pd.DataFrame(stability_rows)
                if not stability.empty:
                    stability["switch_rate"] = (stability["switch_rate"] * 100).round(1)
                    st.caption("Robust selector switching stability")
                    st.dataframe(stability, use_container_width=True, hide_index=True)

        st.subheader("All stage/model metrics")
        metric_display = metrics.copy()
        for column in [
            "rmse",
            "trimmed_rmse_10",
            "mae",
            "median_ae",
            "p90_abs_error",
            "max_abs_error",
            "bias",
            "average_interval_width",
            "median_interval_width",
            "interval_score_80",
            "average_days_to_release",
            "coverage_p_value",
        ]:
            if column in metric_display:
                metric_display[column] = metric_display[column].round(2)
        for column in [
            "direction_accuracy",
            "direction_skill",
            "interval_coverage",
            "raw_interval_coverage",
            "win_rate",
        ]:
            if column in metric_display:
                metric_display[column] = (metric_display[column] * 100).round(1)
        stage_filter = st.multiselect(
            "Forecast stages",
            sorted(metric_display["forecast_stage"].unique()),
            default=sorted(metric_display["forecast_stage"].unique()),
        )
        st.dataframe(
            metric_display.loc[metric_display["forecast_stage"].isin(stage_filter)],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Economic-regime robustness")
        regime_metrics = calculate_stage_regime_metrics(stage_results)
        regime_display = regime_metrics.loc[
            regime_metrics["model_name"] == champion,
            [
                "forecast_stage",
                "sample",
                "observations",
                "rmse",
                "trimmed_rmse_10",
                "mae",
                "median_ae",
                "p90_abs_error",
            "max_abs_error",
                "bias",
                "interval_coverage",
                "average_interval_width",
            ],
        ].copy()
        if regime_display.empty:
            st.info("Regime metrics require the approved staged validation history.")
        else:
            for column in [
                "rmse",
                "trimmed_rmse_10",
                "mae",
                "median_ae",
                "p90_abs_error",
            "max_abs_error",
                "bias",
                "average_interval_width",
            ]:
                regime_display[column] = regime_display[column].round(2)
            regime_display["interval_coverage"] = (
                regime_display["interval_coverage"] * 100
            ).round(1)
            st.dataframe(regime_display, use_container_width=True, hide_index=True)

        notices_json = stage_runs.loc[
            stage_runs["stage_backtest_id"] == selected_stage_id, "notices_json"
        ].iloc[0]
        notices = json.loads(notices_json or "[]")
        if notices:
            with st.expander(f"Pending outcomes and issues ({len(notices)})"):
                st.dataframe(pd.DataFrame(notices), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Automated validation gates")
validation_runs = repository.query_df(
    """
    SELECT validation_id, created_at, model_id, model_version, stage_backtest_id,
           status, passed_gates, total_gates, report_path, summary_json
    FROM validation_runs
    ORDER BY created_at DESC
    LIMIT 30
    """
)

if validation_runs.empty:
    st.info(
        "No automated validation run exists. Run `python scripts\\run_validation.py` "
        "after the staged backtest."
    )
else:
    validation_labels = {
        row["validation_id"]: (
            f"{row['created_at']} | v{row['model_version']} | {row['status']} | "
            f"{row['passed_gates']}/{row['total_gates']} passed"
        )
        for _, row in validation_runs.iterrows()
    }
    selected_validation = st.selectbox(
        "Validation run",
        options=list(validation_labels),
        format_func=lambda value: validation_labels[value],
    )
    run = validation_runs.loc[
        validation_runs["validation_id"] == selected_validation
    ].iloc[0]
    checks = repository.query_df(
        """
        SELECT gate_name, check_name, status, observed_value, threshold, details_json
        FROM validation_checks
        WHERE validation_id = ?
        ORDER BY gate_name, status, check_name
        """,
        [selected_validation],
    )
    passed = int((checks["status"] == "pass").sum())
    failed = int((checks["status"] == "fail").sum())
    warnings = int((checks["status"] == "warning").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", str(run["status"]).upper())
    c2.metric("Passed", passed)
    c3.metric("Failed", failed)
    c4.metric("Warnings", warnings)
    st.dataframe(
        checks.drop(columns=["details_json"]),
        use_container_width=True,
        hide_index=True,
    )
    with st.expander("Validation details"):
        for _, row in checks.iterrows():
            st.markdown(f"**{row['gate_name']} — {row['check_name']}**")
            st.json(json.loads(row["details_json"] or "{}"))
    st.caption(f"Report file: `{run['report_path']}`")

st.divider()
st.subheader("Live forecast registry")
live = repository.query_df(
    """
    SELECT created_at, run_id, model_version, information_cutoff, data_as_of,
           target_period, forecast_stage, champion_model, production_forecast,
           lower_80, upper_80, information_set_hash
    FROM forecast_registry
    ORDER BY created_at DESC
    LIMIT 50
    """
)
if live.empty:
    st.info("Run `python scripts\\run_dfm_nowcast.py` once after installing v0.6.")
else:
    display = live.copy()
    for column in ["production_forecast", "lower_80", "upper_80"]:
        display[column] = display[column].round(2)
    st.dataframe(display, use_container_width=True, hide_index=True)

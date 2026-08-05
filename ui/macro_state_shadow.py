from __future__ import annotations

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.operations.model1d_shadow_monitoring import run_shadow_monitoring

st.title("Model 1D Prospective Transition Shadow")
st.caption(
    "Read-only operations dashboard for the frozen source-versus-rolling-frequency "
    "prospective experiment."
)
st.warning(
    "Research only. This dashboard has no promotion, adaptive switching, blending, "
    "or source-replacement authority."
)

repository = MacroRepository()
repository.initialise()
try:
    result = run_shadow_monitoring(
        repository=repository,
        write_report=False,
    )
except Exception as exc:
    st.error(str(exc))
    st.stop()

readiness = result["readiness"].iloc[0]
metric_columns = st.columns(4)
metric_columns[0].metric("Shadow months", len(result["run_status"]))
metric_columns[1].metric(
    "Complete targets",
    f"{int(readiness['complete_target_months'])}/"
    f"{int(readiness['minimum_complete_target_months'])}",
)
metric_columns[2].metric(
    "Integrity",
    "PASS" if bool(readiness["integrity_pass"]) else "FAIL",
)
metric_columns[3].metric(
    "Comparison",
    "Unlocked" if bool(readiness["comparison_permitted"]) else "Locked",
)

st.caption(
    f"Monitoring as of {result['as_of']} | conclusion status "
    f"{readiness['conclusion_status']} | promotion authority "
    f"{readiness['promotion_authority']}"
)

if result["run_status"].empty:
    st.info("No prospective shadow runs are stored yet.")
else:
    st.subheader("Monthly operational status")
    st.dataframe(
        result["run_status"][
            [
                "state_date",
                "information_cutoff",
                "target_expected_available_date",
                "prediction_count",
                "dimension_count",
                "outcome_count",
                "operational_status",
                "days_to_expected_availability",
            ]
        ].sort_values("state_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    latest_run_id = str(
        result["run_status"].sort_values("state_date").iloc[-1]["shadow_run_id"]
    )
    latest_predictions = result["predictions"].loc[
        result["predictions"]["shadow_run_id"].astype(str) == latest_run_id
    ]
    latest_dimensions = result["dimensions"].loc[
        result["dimensions"]["shadow_run_id"].astype(str) == latest_run_id
    ]

    st.subheader("Latest frozen predictions")
    if latest_predictions.empty:
        st.error("The latest run has no persisted prediction rows.")
    else:
        st.dataframe(
            latest_predictions[
                [
                    "benchmark_id",
                    "predicted_family",
                    "top1_probability",
                    "top2_family",
                    "top2_probability",
                    "entropy",
                    "probability_sum",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Latest frozen dimensions")
    if latest_dimensions.empty:
        st.error("The latest run has no persisted dimension rows.")
    else:
        st.dataframe(
            latest_dimensions[
                [
                    "dimension",
                    "score",
                    "lower_score",
                    "upper_score",
                    "label",
                    "confidence",
                    "source_information_cutoff",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

st.subheader("Integrity checks")
st.dataframe(
    result["integrity_checks"][
        ["check_id", "passed", "observed", "threshold", "interpretation"]
    ],
    use_container_width=True,
    hide_index=True,
)

if not result["benchmark_performance"].empty:
    st.subheader("Descriptive benchmark performance")
    if not bool(readiness["comparison_permitted"]):
        st.info(
            "Performance is displayed descriptively only. The governed comparison "
            "remains locked until at least 12 complete target months exist."
        )
    st.dataframe(
        result["benchmark_performance"],
        use_container_width=True,
        hide_index=True,
    )

if not result["paired_monthly"].empty:
    st.subheader("Resolved monthly comparison")
    paired = result["paired_monthly"].copy()
    paired["state_date"] = pd.to_datetime(paired["state_date"])
    st.line_chart(
        paired.set_index("state_date")[
            ["source_brier_score", "rolling_frequency_brier_score"]
        ]
    )
    st.dataframe(
        paired.sort_values("state_date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

if not result["transition_summary"].empty:
    st.subheader("Transition diagnostics")
    st.dataframe(
        result["transition_summary"],
        use_container_width=True,
        hide_index=True,
    )

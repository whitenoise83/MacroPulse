import json

import pandas as pd
import streamlit as st

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.service import run_macro_state
from macropulse.macro_state.versioning import current_macro_state_identity
from macropulse.settings import settings


st.title("Unified US Macro State — Model 1D")
identity = current_macro_state_identity()
st.caption(
    "Transparent aggregation of the production GDP, inflation, and labour engines"
)
st.warning(
    f"Model 1D v{identity.model_version} is a development foundation. "
    "Its thresholds and regime rules are not yet production validated."
)

repository = MacroRepository()
repository.initialise()

if st.button("Build unified macro state", type="primary"):
    with st.spinner("Selecting production source runs and scoring the macro state..."):
        try:
            result = run_macro_state(repository)
            st.success(f"Unified state completed: {result['run_id']}")
        except Exception as exc:
            st.error(str(exc))

latest = repository.query_df(
    """
    SELECT *
    FROM macro_state_runs
    WHERE status = 'success'
    ORDER BY run_timestamp DESC
    LIMIT 1
    """
)
if latest.empty:
    st.info(
        "Run `python scripts\\run_macro_state.py` after successful production "
        "runs exist for Models 1A, 1B, and 1C."
    )
    st.stop()

run = latest.iloc[0]
dimensions = repository.query_df(
    """
    SELECT *
    FROM macro_state_dimensions
    WHERE run_id = ?
    ORDER BY
        CASE dimension
            WHEN 'growth' THEN 1
            WHEN 'inflation' THEN 2
            WHEN 'labour' THEN 3
            ELSE 4
        END
    """,
    [run["run_id"]],
)
inputs = repository.query_df(
    """
    SELECT *
    FROM macro_state_inputs
    WHERE run_id = ?
    ORDER BY source_model_id, source_target
    """,
    [run["run_id"]],
)
regime = repository.query_df(
    """
    SELECT *
    FROM macro_state_regimes
    WHERE run_id = ? AND is_primary = TRUE
    LIMIT 1
    """,
    [run["run_id"]],
).iloc[0]
metrics = json.loads(run["metrics_json"] or "{}")

st.subheader(str(regime["regime_label"]))
st.write(str(regime["rationale"]))

cols = st.columns(3)
for col, row in zip(cols, dimensions.itertuples(index=False)):
    delta = None if pd.isna(row.delta_score) else f"{row.delta_score:+.2f}"
    col.metric(
        row.dimension.title(),
        f"{row.score:+.2f}",
        delta=delta,
        help=(
            f"Normalized score from -2 to +2. "
            f"80% score range: {row.lower_score:+.2f} to "
            f"{row.upper_score:+.2f}."
        ),
    )
    col.caption(str(row.label))
    col.caption(f"Confidence: {row.confidence:.0f}/100")

st.metric(
    "Overall state confidence",
    f"{float(run['overall_confidence']):.0f}/100",
)
st.caption(
    f"State as of {run['state_as_of']} | source cutoff spread "
    f"{int(run['cutoff_spread_days'])} days"
)

risk_flags = metrics.get("risk_flags", [])
if risk_flags:
    st.subheader("Risk flags")
    for flag in risk_flags:
        st.warning(f"{flag['code']}: {flag['message']}")
else:
    st.success("No configured interval or synchronization risk flags.")

st.subheader("Normalized dimensions")
chart = dimensions.set_index("dimension")[["score"]]
st.bar_chart(chart)

st.subheader("Production source inputs")
st.dataframe(
    inputs[
        [
            "source_model_id",
            "source_model_version",
            "source_target_name",
            "target_period",
            "forecast_stage",
            "point_forecast",
            "lower_80",
            "upper_80",
            "information_cutoff",
        ]
    ].rename(
        columns={
            "source_model_id": "Source model",
            "source_model_version": "Version",
            "source_target_name": "Target",
            "target_period": "Target period",
            "forecast_stage": "Stage",
            "point_forecast": "Point forecast",
            "lower_80": "Lower 80%",
            "upper_80": "Upper 80%",
            "information_cutoff": "Information cutoff",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Provenance"):
    st.write(f"Run ID: `{run['run_id']}`")
    st.write(f"GDP run ID: `{run['gdp_run_id']}`")
    st.write(f"Inflation run ID: `{run['inflation_run_id']}`")
    st.write(f"Labour run ID: `{run['labour_run_id']}`")
    st.write(f"Configuration hash: `{run['config_hash']}`")
    st.write(f"Code hash: `{run['code_hash']}`")
    st.write(f"Source bundle hash: `{run['source_bundle_hash']}`")
    st.write(f"State hash: `{run['state_hash']}`")
    st.write(f"Git commit: `{run['git_commit']}`")

st.divider()
st.header("Historical pseudo-real-time reconstruction")

history_run = repository.query_df(
    """
    SELECT *
    FROM macro_state_history_runs
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if history_run.empty:
    st.info(
        "Run `python scripts\\run_macro_state_history.py --start 2015-01-01 "
        "--end 2026-08-01` to build the first historical reconstruction."
    )
else:
    history_meta = history_run.iloc[0]
    history_states = repository.query_df(
        """
        SELECT *
        FROM macro_state_history_states
        WHERE reconstruction_id = ?
        ORDER BY state_date
        """,
        [history_meta["reconstruction_id"]],
    )
    st.caption(
        f"{history_meta['start_date']} to {history_meta['end_date']} | "
        f"{int(history_meta['months_reconstructed'])} reconstructed months | "
        f"Coverage {float(history_meta['coverage_ratio'] or 0):.1%} | "
        f"Longest contiguous run "
        f"{int(history_meta['longest_contiguous_months'] or 0)} months | "
        f"Source mode {history_meta['source_mode'] or 'legacy'} | "
        f"No-look-ahead audit: "
        f"{'pass' if history_meta['no_look_ahead_pass'] else 'fail'}"
    )

    score_chart = history_states.set_index("state_date")[
        ["growth_score", "inflation_score", "labour_score"]
    ]
    st.line_chart(score_chart)

    regime_counts = (
        history_states["primary_regime_label"]
        .value_counts()
        .rename_axis("Regime")
        .reset_index(name="Months")
    )
    st.subheader("Regime frequency")
    st.dataframe(
        regime_counts,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Latest historical states")
    st.dataframe(
        history_states[
            [
                "state_date",
                "growth_score",
                "inflation_score",
                "labour_score",
                "primary_regime_label",
                "possible_regime_count",
                "source_cutoff_spread_days",
            ]
        ].tail(24),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.header("Model 1D specification tournament")
st.caption(
    "Chronological normalization, weighting, threshold, and uncertainty "
    "comparison. The winner remains provisional."
)

if st.button("Run Model 1D tournament"):
    from macropulse.macro_state.tournament_service import (
        run_macro_state_tournament,
    )

    with st.spinner(
        "Evaluating core specifications and uncertainty candidates..."
    ):
        try:
            tournament_result = run_macro_state_tournament(repository)
            st.success(
                "Tournament complete: "
                f"{tournament_result['tournament_id']}"
            )
        except Exception as exc:
            st.error(str(exc))

tournament_run = repository.query_df(
    """
    SELECT *
    FROM macro_state_tournament_runs
    WHERE status = 'success'
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if tournament_run.empty:
    st.info(
        "Run `python scripts\\run_macro_state_tournament.py` after the "
        "production-vintage history has been reconstructed."
    )
else:
    tournament_meta = tournament_run.iloc[0]
    tournament_id = str(tournament_meta["tournament_id"])
    st.subheader("Provisional tournament winner")
    winner_cols = st.columns(4)
    winner_cols[0].metric(
        "Validation score",
        f"{float(tournament_meta['selected_validation_score']):.1f}",
    )
    winner_cols[1].metric(
        "Holdout rank",
        int(tournament_meta["selected_holdout_rank"]),
    )
    winner_cols[2].metric(
        "Core candidates",
        int(tournament_meta["core_candidates"]),
    )
    winner_cols[3].metric(
        "Uncertainty candidates",
        int(tournament_meta["uncertainty_candidates"]),
    )
    st.code(str(tournament_meta["selected_candidate_id"]))
    st.warning(
        "This is a research-tournament winner, not an approved Model 1D "
        "candidate or production policy."
    )

    final_candidates = repository.query_df(
        """
        SELECT *
        FROM macro_state_tournament_candidates
        WHERE tournament_id = ?
          AND candidate_type = 'uncertainty'
        ORDER BY validation_rank, candidate_id
        """,
        [tournament_id],
    )
    final_metrics = repository.query_df(
        """
        SELECT *
        FROM macro_state_tournament_metrics
        WHERE tournament_id = ?
          AND candidate_id IN (
              SELECT candidate_id
              FROM macro_state_tournament_candidates
              WHERE tournament_id = ?
                AND candidate_type = 'uncertainty'
          )
        ORDER BY candidate_id, split
        """,
        [tournament_id, tournament_id],
    )
    leaderboard = final_candidates.merge(
        final_metrics.loc[final_metrics["split"] == "validation"][
            [
                "candidate_id",
                "brier_score",
                "log_loss",
                "coverage_80",
                "top1_accuracy",
                "exact_regime_accuracy",
            ]
        ],
        on="candidate_id",
        how="left",
    )
    st.subheader("Final validation leaderboard")
    st.dataframe(
        leaderboard[
            [
                "validation_rank",
                "candidate_id",
                "normalization_id",
                "inflation_weights_id",
                "labour_weights_id",
                "threshold_id",
                "uncertainty_id",
                "validation_score",
                "holdout_rank",
                "holdout_score",
                "exact_regime_accuracy",
                "brier_score",
                "log_loss",
                "coverage_80",
                "top1_accuracy",
            ]
        ].head(15),
        use_container_width=True,
        hide_index=True,
    )

    selected_monthly = repository.query_df(
        """
        SELECT *
        FROM macro_state_tournament_monthly
        WHERE tournament_id = ?
          AND candidate_id = ?
        ORDER BY state_date
        """,
        [
            tournament_id,
            tournament_meta["selected_candidate_id"],
        ],
    )
    if not selected_monthly.empty:
        st.subheader("Selected specification: forecast versus realised scores")
        st.line_chart(
            selected_monthly.set_index("state_date")[
                [
                    "forecast_growth",
                    "actual_growth",
                    "forecast_inflation",
                    "actual_inflation",
                    "forecast_labour",
                    "actual_labour",
                ]
            ]
        )
        st.subheader("Selected specification: recent uncertainty audit")
        st.dataframe(
            selected_monthly[
                [
                    "state_date",
                    "split",
                    "forecast_regime",
                    "actual_regime",
                    "top_regime",
                    "top_probability",
                    "actual_regime_probability",
                    "coverage_80",
                    "effective_regimes",
                ]
            ].tail(24),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.header("Model 1D rolling-origin stability tournament")
st.caption(
    "Expanding-window fold stability for normalization, weighting, thresholds, "
    "and uncertainty. The 2024-08 to 2026-03 audit period is consumed and is "
    "reported separately from selection."
)

if st.button("Run Model 1D stability tournament"):
    from macropulse.macro_state.rolling_tournament_service import (
        run_macro_state_stability_tournament,
    )

    with st.spinner("Evaluating rolling-origin folds and stability gates..."):
        try:
            stability_result = run_macro_state_stability_tournament(repository)
            st.success(
                "Stability tournament complete: "
                f"{stability_result['stability_id']}"
            )
        except Exception as exc:
            st.error(str(exc))

stability_run = repository.query_df(
    """
    SELECT *
    FROM macro_state_stability_runs
    WHERE status = 'success'
    ORDER BY created_at DESC
    LIMIT 1
    """
)
if stability_run.empty:
    st.info(
        "Run `python scripts\\run_macro_state_stability_tournament.py` after "
        "the v0.3 research tournament has been completed."
    )
else:
    stability_meta = stability_run.iloc[0]
    stability_id = str(stability_meta["stability_id"])
    st.subheader("Rolling-origin research leader")
    stability_cols = st.columns(5)
    stability_cols[0].metric(
        "Stability score",
        f"{float(stability_meta['selected_stability_score']):.1f}",
    )
    stability_cols[1].metric(
        "Rolling folds",
        int(stability_meta["fold_count"]),
    )
    stability_cols[2].metric(
        "Audit rank",
        int(stability_meta["selected_audit_rank"]),
    )
    stability_cols[3].metric(
        "Core candidates",
        int(stability_meta["core_candidates"]),
    )
    stability_cols[4].metric(
        "Final candidates",
        int(stability_meta["final_candidates"]),
    )
    st.code(str(stability_meta["selected_candidate_id"]))
    if bool(stability_meta["selected_governance_pass"]):
        st.success(
            "The research leader passes the configured v0.3.1 stability "
            "gates. This is not candidate or production approval."
        )
    else:
        st.warning(
            "The research leader fails one or more stability gates and must "
            "not be promoted."
        )

    stability_folds = repository.query_df(
        """
        SELECT *
        FROM macro_state_stability_folds
        WHERE stability_id = ?
        ORDER BY fold_id
        """,
        [stability_id],
    )
    st.subheader("Rolling-origin folds")
    st.dataframe(
        stability_folds[
            [
                "fold_id",
                "training_start",
                "training_end",
                "training_months",
                "evaluation_start",
                "evaluation_end",
                "evaluation_months",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    stability_candidates = repository.query_df(
        """
        SELECT *
        FROM macro_state_stability_candidates
        WHERE stability_id = ?
          AND candidate_type = 'final'
        ORDER BY stability_rank, candidate_id
        """,
        [stability_id],
    )
    st.subheader("Final stability leaderboard")
    st.dataframe(
        stability_candidates[
            [
                "stability_rank",
                "candidate_id",
                "stability_score",
                "median_fold_rank",
                "worst_fold_rank",
                "leading_third_rate",
                "baseline_dominance_rate",
                "uncertainty_method_win_rate",
                "bootstrap_margin_lower",
                "audit_final_rank",
                "governance_pass",
            ]
        ].head(15),
        use_container_width=True,
        hide_index=True,
    )

    selected_fold_metrics = repository.query_df(
        """
        SELECT *
        FROM macro_state_stability_fold_metrics
        WHERE stability_id = ?
          AND candidate_id = ?
          AND candidate_type = 'final'
        ORDER BY fold_id
        """,
        [stability_id, stability_meta["selected_candidate_id"]],
    )
    st.subheader("Selected candidate by fold")
    st.dataframe(
        selected_fold_metrics[
            [
                "fold_id",
                "evaluation_start",
                "evaluation_end",
                "rank",
                "score",
                "exact_regime_accuracy",
                "strongest_baseline",
                "strongest_baseline_accuracy",
                "baseline_margin",
                "brier_score",
                "log_loss",
                "coverage_80",
                "uncertainty_method_rank",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    audit_metrics = repository.query_df(
        """
        SELECT *
        FROM macro_state_stability_audit_metrics
        WHERE stability_id = ?
        ORDER BY audit_final_rank, candidate_id
        """,
        [stability_id],
    )
    st.subheader("Consumed audit leaderboard")
    st.caption("Reported for external audit only; not used for ranking.")
    st.dataframe(
        audit_metrics[
            [
                "audit_final_rank",
                "candidate_id",
                "audit_final_score",
                "audit_exact_regime_accuracy",
                "audit_baseline_accuracy",
                "audit_baseline_margin",
                "audit_brier_score",
                "audit_log_loss",
                "audit_coverage_80",
                "audit_top1_accuracy",
            ]
        ].head(15),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.header("Model 1D regime-target and temporal-decision diagnostics")
st.caption(
    "Diagnoses continuous-score performance, eight-regime classification, "
    "turning-point detection, and four causal temporal decision policies. "
    "The v0.3.1 source candidate and consumed audit remain research-only."
)

if st.button("Run Model 1D temporal diagnostics"):
    from macropulse.macro_state.temporal_diagnostics_service import (
        run_macro_state_temporal_diagnostics,
    )

    with st.spinner("Evaluating temporal policies and transition diagnostics..."):
        try:
            temporal_result = run_macro_state_temporal_diagnostics(repository)
            st.success(
                "Temporal diagnostics complete: "
                f"{temporal_result['diagnostic_id']}"
            )
            temporal_cols = st.columns(4)
            temporal_cols[0].metric(
                "Research leader",
                temporal_result["selected_policy_id"],
            )
            temporal_cols[1].metric(
                "Stability score",
                f"{temporal_result['selected_stability_score']:.1f}",
            )
            temporal_cols[2].metric(
                "Consumed-audit rank",
                temporal_result["selected_audit_rank"],
            )
            temporal_cols[3].metric(
                "Governance gate",
                "Pass" if temporal_result["selected_governance_pass"] else "Fail",
            )
            st.subheader("Temporal policy stability leaderboard")
            st.dataframe(
                temporal_result["policy_stability"][
                    [
                        "stability_rank",
                        "policy_id",
                        "stability_score",
                        "median_fold_rank",
                        "baseline_dominance_rate",
                        "mean_exact_regime_accuracy",
                        "mean_family_accuracy",
                        "mean_transition_f1",
                        "mean_false_transition_rate",
                        "bootstrap_margin_lower",
                        "audit_rank",
                        "governance_pass",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.subheader("Source target decomposition")
            st.dataframe(
                temporal_result["target_selection"],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Report: {temporal_result['report_path']}")
        except Exception as exc:
            st.error(str(exc))

latest_temporal_reports = sorted(
    (settings.project_root / "reports" / "macro_state_temporal").glob(
        "model1d_temporal_*.md"
    ),
    key=lambda path: path.stat().st_mtime,
    reverse=True,
) if (settings.project_root / "reports" / "macro_state_temporal").exists() else []
if latest_temporal_reports:
    st.info(f"Latest temporal diagnostic report: {latest_temporal_reports[0]}")

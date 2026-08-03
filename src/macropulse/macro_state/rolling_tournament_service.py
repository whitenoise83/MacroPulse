from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.rolling_tournament import (
    attach_bootstrap_intervals,
    run_rolling_core_tournament,
    run_rolling_uncertainty_tournament,
    selected_subperiod_metrics,
)
from macropulse.macro_state.tournament import load_tournament_dataset
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "No rows."
    data = frame[columns].copy()
    headers = [str(item) for item in data.columns]
    output = ["| " + " | ".join(headers) + " |"]
    output.append("| " + " | ".join("---" for _ in headers) + " |")
    for record in data.itertuples(index=False):
        values: list[str] = []
        for value in record:
            if isinstance(value, (float, np.floating)):
                values.append(f"{float(value):.4f}")
            else:
                values.append(str(value))
        output.append("| " + " | ".join(values) + " |")
    return "\n".join(output)


def _latest_source_tournament_id(
    repository: MacroRepository,
    reconstruction_id: str,
) -> str | None:
    frame = repository.query_df(
        """
        SELECT tournament_id
        FROM macro_state_tournament_runs
        WHERE reconstruction_id = ?
          AND status = 'success'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [reconstruction_id],
    )
    if frame.empty:
        return None
    return str(frame.iloc[0]["tournament_id"])


def _fold_table(
    stability_id: str,
    created_at: pd.Timestamp,
    plan: Any,
) -> pd.DataFrame:
    rows = []
    for fold in plan.folds:
        rows.append(
            {
                "stability_id": stability_id,
                **fold.as_dict(),
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def _candidate_table(
    *,
    stability_id: str,
    created_at: pd.Timestamp,
    selected_candidate_id: str,
    core_stability: pd.DataFrame,
    final_stability: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    common_columns = [
        "folds", "mean_fold_score", "median_fold_score",
        "mean_fold_rank", "median_fold_rank", "rank_std",
        "best_fold_rank", "worst_fold_rank", "fold_win_rate",
        "leading_third_rate", "catastrophic_fold_count",
        "baseline_dominance_rate", "mean_baseline_margin",
        "average_regret", "regime_collapse_fold_rate",
    ]
    for row in core_stability.itertuples(index=False):
        payload = row._asdict()
        rows.append(
            {
                "stability_id": stability_id,
                "candidate_id": str(row.candidate_id),
                "candidate_type": "core",
                "core_candidate_id": str(row.candidate_id),
                "uncertainty_id": None,
                "selected": False,
                "governance_pass": bool(row.governance_pass),
                "stability_rank": int(row.stability_rank),
                "stability_score": float(row.stability_score),
                **{key: payload[key] for key in common_columns},
                "uncertainty_method_win_rate": None,
                "proper_score_dominance_rate": None,
                "bootstrap_margin_mean": None,
                "bootstrap_margin_lower": None,
                "bootstrap_margin_upper": None,
                "audit_final_score": None,
                "audit_final_rank": None,
                "audit_exact_regime_accuracy": None,
                "audit_brier_score": None,
                "audit_log_loss": None,
                "audit_coverage_80": None,
                "audit_top1_accuracy": None,
                "audit_baseline_margin": None,
                "metrics_json": json.dumps(payload, sort_keys=True, default=str),
                "created_at": created_at,
            }
        )
    for row in final_stability.itertuples(index=False):
        payload = row._asdict()
        rows.append(
            {
                "stability_id": stability_id,
                "candidate_id": str(row.candidate_id),
                "candidate_type": "final",
                "core_candidate_id": str(row.core_candidate_id),
                "uncertainty_id": str(row.uncertainty_id),
                "selected": str(row.candidate_id) == selected_candidate_id,
                "governance_pass": bool(row.governance_pass),
                "stability_rank": int(row.stability_rank),
                "stability_score": float(row.stability_score),
                **{key: payload[key] for key in common_columns},
                "uncertainty_method_win_rate": float(
                    row.uncertainty_method_win_rate
                ),
                "proper_score_dominance_rate": float(
                    row.proper_score_dominance_rate
                ),
                "bootstrap_margin_mean": float(row.bootstrap_margin_mean),
                "bootstrap_margin_lower": float(row.bootstrap_margin_lower),
                "bootstrap_margin_upper": float(row.bootstrap_margin_upper),
                "audit_final_score": float(row.audit_final_score),
                "audit_final_rank": int(row.audit_final_rank),
                "audit_exact_regime_accuracy": float(
                    row.audit_exact_regime_accuracy
                ),
                "audit_brier_score": float(row.audit_brier_score),
                "audit_log_loss": float(row.audit_log_loss),
                "audit_coverage_80": float(row.audit_coverage_80),
                "audit_top1_accuracy": float(row.audit_top1_accuracy),
                "audit_baseline_margin": float(row.audit_baseline_margin),
                "metrics_json": json.dumps(payload, sort_keys=True, default=str),
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def _fold_metric_table(
    *,
    stability_id: str,
    created_at: pd.Timestamp,
    core_fold_metrics: pd.DataFrame,
    final_fold_metrics: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate_type, frame in (
        ("core", core_fold_metrics),
        ("final", final_fold_metrics),
    ):
        for row in frame.itertuples(index=False):
            values = row._asdict()
            is_final = candidate_type == "final"
            rows.append(
                {
                    "stability_id": stability_id,
                    "fold_id": str(row.fold_id),
                    "candidate_id": str(row.candidate_id),
                    "candidate_type": candidate_type,
                    "core_candidate_id": str(
                        row.core_candidate_id if is_final else row.candidate_id
                    ),
                    "uncertainty_id": (
                        str(row.uncertainty_id) if is_final else None
                    ),
                    "evaluation_start": row.evaluation_start,
                    "evaluation_end": row.evaluation_end,
                    "evaluation_months": int(row.evaluation_months),
                    "score": float(
                        row.final_score if is_final else row.core_score
                    ),
                    "rank": int(
                        row.final_rank if is_final else row.core_rank
                    ),
                    "core_score": float(row.core_score),
                    "uncertainty_score": (
                        float(row.uncertainty_score) if is_final else None
                    ),
                    "dimension_rmse": float(row.dimension_rmse),
                    "exact_regime_accuracy": float(
                        row.exact_regime_accuracy
                    ),
                    "family_accuracy": float(row.family_accuracy),
                    "sign_accuracy": float(row.sign_accuracy),
                    "regime_collapse_penalty": float(
                        row.regime_collapse_penalty
                    ),
                    "brier_score": (
                        float(row.brier_score) if is_final else None
                    ),
                    "log_loss": float(row.log_loss) if is_final else None,
                    "coverage_80": (
                        float(row.coverage_80) if is_final else None
                    ),
                    "top1_accuracy": (
                        float(row.top1_accuracy) if is_final else None
                    ),
                    "mode_accuracy": float(row.mode_accuracy),
                    "persistence_accuracy": float(row.persistence_accuracy),
                    "strongest_baseline": str(row.strongest_baseline),
                    "strongest_baseline_accuracy": float(
                        row.strongest_baseline_accuracy
                    ),
                    "baseline_margin": float(row.baseline_margin),
                    "beats_strongest_baseline": bool(
                        row.beats_strongest_baseline
                    ),
                    "uncertainty_method_rank": (
                        int(row.uncertainty_method_rank)
                        if is_final else None
                    ),
                    "proper_score_improvement": (
                        float(row.proper_score_improvement)
                        if is_final else None
                    ),
                    "proper_score_dominates": (
                        bool(row.proper_score_dominates)
                        if is_final else None
                    ),
                    "created_at": created_at,
                }
            )
    return pd.DataFrame(rows)


def _audit_table(
    stability_id: str,
    created_at: pd.Timestamp,
    audit: pd.DataFrame,
) -> pd.DataFrame:
    frame = audit.copy()
    frame.insert(0, "stability_id", stability_id)
    frame["created_at"] = created_at
    return frame


def _subperiod_table(
    stability_id: str,
    candidate_id: str,
    created_at: pd.Timestamp,
    subperiods: pd.DataFrame,
) -> pd.DataFrame:
    frame = subperiods.copy()
    frame.insert(0, "stability_id", stability_id)
    frame.insert(1, "candidate_id", candidate_id)
    frame["created_at"] = created_at
    return frame


def _selected_gate_failures(
    selected: pd.Series,
    config: dict[str, Any],
) -> list[str]:
    section = config["stability_tournament"]
    failures: list[str] = []
    if float(selected["median_fold_rank"]) > float(
        selected["leading_third_cutoff"]
    ):
        failures.append("median fold rank is outside the leading third")
    if int(selected["catastrophic_fold_count"]) > 0:
        failures.append("at least one catastrophic bottom-tail fold occurred")
    if float(selected["leading_third_rate"]) < float(
        section["minimum_leading_third_rate"]
    ):
        failures.append("leading-third fold rate is below the gate")
    if float(selected["baseline_dominance_rate"]) < float(
        section["minimum_baseline_dominance_rate"]
    ):
        failures.append("naive-baseline dominance rate is below the gate")
    if float(selected["uncertainty_method_win_rate"]) < float(
        section["minimum_uncertainty_method_win_rate"]
    ):
        failures.append("uncertainty-method fold win rate is below the gate")
    if (
        str(selected["uncertainty_id"]) != "independent_normal"
        and float(selected["proper_score_dominance_rate"])
        < float(section["minimum_proper_score_dominance_rate"])
    ):
        failures.append("proper-score dominance over independence is insufficient")
    if float(selected["regime_collapse_fold_rate"]) > float(
        section["maximum_regime_collapse_fold_rate"]
    ):
        failures.append("regime-collapse fold rate exceeds the gate")
    if float(selected["bootstrap_margin_lower"]) <= float(
        section["minimum_bootstrap_margin_lower"]
    ):
        failures.append("block-bootstrap baseline margin is not strictly positive")
    return failures


def _write_report(
    *,
    stability_id: str,
    identity: Any,
    reconstruction_id: str,
    source_tournament_id: str | None,
    plan: Any,
    selected: pd.Series,
    gate_failures: list[str],
    core_stability: pd.DataFrame,
    final_stability: pd.DataFrame,
    final_fold_metrics: pd.DataFrame,
    audit: pd.DataFrame,
    subperiods: pd.DataFrame,
) -> Path:
    report_dir = settings.project_root / "reports" / "macro_state_stability"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"model1d_stability_{stability_id}.md"
    selected_folds = final_fold_metrics.loc[
        final_fold_metrics["candidate_id"] == selected["candidate_id"]
    ].sort_values("fold_id")
    failures = (
        "\n".join(f"- {item}" for item in gate_failures)
        if gate_failures else "- None"
    )
    report = f"""# Model 1D v0.3.1 Rolling-Origin Stability Report

- Stability tournament ID: `{stability_id}`
- Reconstruction ID: `{reconstruction_id}`
- Source v0.3 tournament ID: `{source_tournament_id}`
- Model: `{identity.model_id}` v`{identity.model_version}`
- Status: research stability tournament; not candidate or production approved

## Design

- Selection sample: {plan.selection_dates[0]} to {plan.selection_dates[-1]} ({len(plan.selection_dates)} complete states)
- Rolling folds: {len(plan.folds)}
- Evaluation window: {len(plan.folds[0].evaluation_dates)} states
- Audit sample: {plan.audit_dates[0]} to {plan.audit_dates[-1]} ({len(plan.audit_dates)} complete states)
- Audit status: consumed external audit; reported but not used for ranking

## Research stability leader

- Candidate: `{selected['candidate_id']}`
- Core: `{selected['core_candidate_id']}`
- Uncertainty: `{selected['uncertainty_id']}`
- Stability score: {float(selected['stability_score']):.2f}
- Median fold rank: {float(selected['median_fold_rank']):.1f}
- Worst fold rank: {int(selected['worst_fold_rank'])}
- Leading-third rate: {float(selected['leading_third_rate']):.1%}
- Baseline dominance rate: {float(selected['baseline_dominance_rate']):.1%}
- Uncertainty-method win rate: {float(selected['uncertainty_method_win_rate']):.1%}
- Bootstrap baseline margin: {float(selected['bootstrap_margin_mean']):.3f} [{float(selected['bootstrap_margin_lower']):.3f}, {float(selected['bootstrap_margin_upper']):.3f}]
- Audit rank: {int(selected['audit_final_rank'])} of {len(final_stability)}
- Governance gate: {'pass' if bool(selected['governance_pass']) else 'fail'}

## Gate failures

{failures}

## Core stability leaderboard

{_markdown_table(core_stability.head(15), [
    'stability_rank', 'candidate_id', 'stability_score',
    'median_fold_rank', 'worst_fold_rank', 'leading_third_rate',
    'baseline_dominance_rate', 'rank_std', 'average_regret',
    'regime_collapse_fold_rate', 'governance_pass'
])}

## Final stability leaderboard

{_markdown_table(final_stability.head(15), [
    'stability_rank', 'candidate_id', 'stability_score',
    'median_fold_rank', 'worst_fold_rank', 'leading_third_rate',
    'baseline_dominance_rate', 'uncertainty_method_win_rate',
    'proper_score_dominance_rate', 'bootstrap_margin_lower',
    'audit_final_rank', 'governance_pass'
])}

## Selected candidate by fold

{_markdown_table(selected_folds, [
    'fold_id', 'evaluation_start', 'evaluation_end', 'final_rank',
    'final_score', 'exact_regime_accuracy', 'strongest_baseline',
    'strongest_baseline_accuracy', 'baseline_margin', 'brier_score',
    'log_loss', 'coverage_80', 'uncertainty_method_rank'
])}

## Consumed audit leaderboard

{_markdown_table(audit.head(15), [
    'audit_final_rank', 'candidate_id', 'audit_final_score',
    'audit_exact_regime_accuracy', 'audit_baseline_accuracy',
    'audit_baseline_margin', 'audit_brier_score', 'audit_log_loss',
    'audit_coverage_80', 'audit_top1_accuracy'
])}

## Selected candidate by macro subperiod

{_markdown_table(subperiods, [
    'subperiod_id', 'start_date', 'end_date', 'months',
    'dimension_rmse', 'exact_regime_accuracy', 'family_accuracy',
    'brier_score', 'log_loss', 'coverage_80', 'top1_accuracy'
])}

## Governance interpretation

The rolling-origin ranking replaces the unstable single validation split from
v0.3.0. The audit period has already been observed and is not used to select
the research leader. Passing this research tournament does not itself approve
a Model 1D candidate. Failure of any gate blocks candidate promotion.
"""
    report_path.write_text(report, encoding="utf-8")
    return report_path


def run_macro_state_stability_tournament(
    repository: MacroRepository | None = None,
    reconstruction_id: str | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    resolved_reconstruction, dataset = load_tournament_dataset(
        repository, reconstruction_id
    )
    source_tournament_id = _latest_source_tournament_id(
        repository, resolved_reconstruction
    )
    (
        plan,
        core_candidates,
        monthly_by_candidate,
        core_fold_metrics,
        core_stability,
    ) = run_rolling_core_tournament(dataset, config)
    (
        final_stability,
        final_fold_metrics,
        monthly_final,
        audit,
    ) = run_rolling_uncertainty_tournament(
        core_candidates=core_candidates,
        monthly_by_candidate=monthly_by_candidate,
        core_fold_metrics=core_fold_metrics,
        core_stability=core_stability,
        plan=plan,
        config=config,
    )
    final_stability = attach_bootstrap_intervals(
        final_stability,
        final_fold_metrics=final_fold_metrics,
        monthly_final=monthly_final,
        plan=plan,
        config=config,
    )
    threshold = float(
        config["stability_tournament"]["minimum_bootstrap_margin_lower"]
    )
    final_stability["governance_pass"] = (
        final_stability["governance_pass"].astype(bool)
        & (final_stability["bootstrap_margin_lower"] > threshold)
    )
    final_stability = final_stability.sort_values(
        ["stability_rank", "candidate_id"]
    ).reset_index(drop=True)
    selected = final_stability.iloc[0]
    selected_id = str(selected["candidate_id"])
    gate_failures = _selected_gate_failures(selected, config)
    selected_monthly = monthly_final[selected_id]
    subperiods = selected_subperiod_metrics(selected_monthly, config)

    stability_id = str(uuid.uuid4())
    created_at = pd.Timestamp.now(tz="UTC").tz_localize(None)
    report_path = _write_report(
        stability_id=stability_id,
        identity=identity,
        reconstruction_id=resolved_reconstruction,
        source_tournament_id=source_tournament_id,
        plan=plan,
        selected=selected,
        gate_failures=gate_failures,
        core_stability=core_stability,
        final_stability=final_stability,
        final_fold_metrics=final_fold_metrics,
        audit=audit,
        subperiods=subperiods,
    )
    warnings: list[str] = []
    if not bool(selected["governance_pass"]):
        warnings.append(
            "The research stability leader fails one or more candidate gates."
        )
    leading_audit_cutoff = max(1, int(math.ceil(len(audit) / 3)))
    if int(selected["audit_final_rank"]) > leading_audit_cutoff:
        warnings.append(
            "The stability leader ranks outside the leading audit third."
        )
    if float(selected["bootstrap_margin_lower"]) <= 0.0:
        warnings.append(
            "The block-bootstrap accuracy margin versus the strongest naive "
            "baseline includes zero or worse."
        )

    run_record = pd.DataFrame(
        [
            {
                "stability_id": stability_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "reconstruction_id": resolved_reconstruction,
                "source_tournament_id": source_tournament_id,
                "created_at": created_at,
                "status": "success",
                "fold_count": len(plan.folds),
                "selection_start": plan.selection_dates[0],
                "selection_end": plan.selection_dates[-1],
                "selection_months": len(plan.selection_dates),
                "audit_start": plan.audit_dates[0],
                "audit_end": plan.audit_dates[-1],
                "audit_months": len(plan.audit_dates),
                "core_candidates": len(core_candidates),
                "final_candidates": len(final_stability),
                "selected_candidate_id": selected_id,
                "selected_core_candidate_id": str(
                    selected["core_candidate_id"]
                ),
                "selected_uncertainty_id": str(selected["uncertainty_id"]),
                "selected_stability_score": float(
                    selected["stability_score"]
                ),
                "selected_stability_rank": int(selected["stability_rank"]),
                "selected_governance_pass": bool(
                    selected["governance_pass"]
                ),
                "selected_audit_rank": int(selected["audit_final_rank"]),
                "config_hash": identity.config_hash,
                "code_hash": identity.code_hash,
                "git_commit": identity.git_commit,
                "warnings_json": json.dumps(warnings, sort_keys=True),
                "report_path": str(report_path),
                "notes": (
                    "Model 1D v0.3.1 rolling-origin stability tournament. "
                    "The audit period is consumed and not used for ranking."
                ),
            }
        ]
    )
    folds = _fold_table(stability_id, created_at, plan)
    candidates = _candidate_table(
        stability_id=stability_id,
        created_at=created_at,
        selected_candidate_id=selected_id,
        core_stability=core_stability,
        final_stability=final_stability,
    )
    fold_metrics = _fold_metric_table(
        stability_id=stability_id,
        created_at=created_at,
        core_fold_metrics=core_fold_metrics,
        final_fold_metrics=final_fold_metrics,
    )
    audit_metrics = _audit_table(stability_id, created_at, audit)
    subperiod_metrics = _subperiod_table(
        stability_id, selected_id, created_at, subperiods
    )
    repository.save_macro_state_stability_tournament(
        run_record=run_record,
        folds=folds,
        candidates=candidates,
        fold_metrics=fold_metrics,
        audit_metrics=audit_metrics,
        subperiod_metrics=subperiod_metrics,
    )
    return {
        "stability_id": stability_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "reconstruction_id": resolved_reconstruction,
        "source_tournament_id": source_tournament_id,
        "plan": plan,
        "core_candidates": len(core_candidates),
        "final_candidates": len(final_stability),
        "selected_candidate_id": selected_id,
        "selected_core_candidate_id": str(selected["core_candidate_id"]),
        "selected_uncertainty_id": str(selected["uncertainty_id"]),
        "selected_stability_score": float(selected["stability_score"]),
        "selected_governance_pass": bool(selected["governance_pass"]),
        "selected_audit_rank": int(selected["audit_final_rank"]),
        "gate_failures": gate_failures,
        "warnings": warnings,
        "core_stability": core_stability,
        "final_stability": final_stability,
        "selected_fold_metrics": final_fold_metrics.loc[
            final_fold_metrics["candidate_id"] == selected_id
        ].sort_values("fold_id"),
        "audit": audit,
        "subperiods": subperiods,
        "report_path": report_path,
    }

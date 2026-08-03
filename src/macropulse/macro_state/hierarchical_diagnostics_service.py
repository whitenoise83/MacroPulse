from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.hierarchical_diagnostics import (
    build_hierarchical_candidates,
    confusion_table,
    expanding_candidate_frame,
    governance_failures,
    per_regime_metrics,
    run_hierarchical_diagnostics,
)
from macropulse.macro_state.temporal_diagnostics import (
    source_candidate_monthly,
    temporal_plan,
    transition_events,
)
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _markdown(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No rows._"
    return frame[columns].to_markdown(index=False)


def _write_outputs(
    *,
    diagnostic_id: str,
    identity: Any,
    source: Any,
    plan: Any,
    selected: pd.Series,
    gate_failures: list[str],
    stability: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    calibration_metrics: pd.DataFrame,
    audit: pd.DataFrame,
    selected_regimes: pd.DataFrame,
    selected_confusion: pd.DataFrame,
    selected_transitions: pd.DataFrame,
    selected_expanding: pd.DataFrame,
    selected_expanding_calibration: pd.DataFrame,
) -> tuple[Path, dict[str, Path]]:
    report_dir = settings.project_root / "reports" / "macro_state_hierarchical"
    report_dir.mkdir(parents=True, exist_ok=True)
    prefix = report_dir / f"model1d_hierarchical_{diagnostic_id}"
    paths = {
        "stability": prefix.with_name(prefix.name + "_stability.csv"),
        "fold_metrics": prefix.with_name(prefix.name + "_fold_metrics.csv"),
        "calibration_metrics": prefix.with_name(
            prefix.name + "_calibration_metrics.csv"
        ),
        "audit": prefix.with_name(prefix.name + "_audit.csv"),
        "selected_regimes": prefix.with_name(
            prefix.name + "_selected_regimes.csv"
        ),
        "selected_confusion": prefix.with_name(
            prefix.name + "_selected_confusion.csv"
        ),
        "selected_transitions": prefix.with_name(
            prefix.name + "_selected_transitions.csv"
        ),
        "selected_monthly": prefix.with_name(
            prefix.name + "_selected_monthly.csv"
        ),
        "selected_expanding_calibration": prefix.with_name(
            prefix.name + "_selected_expanding_calibration.csv"
        ),
    }
    stability.to_csv(paths["stability"], index=False)
    fold_metrics.to_csv(paths["fold_metrics"], index=False)
    calibration_metrics.to_csv(paths["calibration_metrics"], index=False)
    audit.to_csv(paths["audit"], index=False)
    selected_regimes.to_csv(paths["selected_regimes"], index=False)
    selected_confusion.to_csv(paths["selected_confusion"], index=False)
    selected_transitions.to_csv(paths["selected_transitions"], index=False)
    selected_expanding.to_csv(paths["selected_monthly"], index=False)
    selected_expanding_calibration.to_csv(
        paths["selected_expanding_calibration"], index=False
    )

    failures = (
        "\n".join(f"- {item}" for item in gate_failures)
        if gate_failures
        else "- None"
    )
    selected_folds = fold_metrics.loc[
        fold_metrics["candidate_id"] == selected["candidate_id"]
    ].sort_values("fold_id")
    calibration_summary = (
        calibration_metrics.loc[
            calibration_metrics["candidate_id"] == selected["candidate_id"]
        ]
        .groupby("dimension", as_index=False)
        .agg(
            mean_pre_bias=("pre_bias", "mean"),
            mean_post_bias=("post_bias", "mean"),
            mean_alpha=("alpha", "mean"),
            mean_beta=("beta", "mean"),
        )
    )
    report = f"""# Model 1D v0.3.3 Causal Calibration and Hierarchical Regime Diagnostics

- Diagnostic ID: `{diagnostic_id}`
- Source stability run: `{source.stability_id}`
- Source candidate: `{source.candidate_id}`
- Reconstruction ID: `{source.reconstruction_id}`
- Model: `{identity.model_id}` v`{identity.model_version}`
- Status: research diagnostics only; not candidate or production approved

## Design

- Selection sample: {plan.selection_dates[0]} to {plan.selection_dates[-1]} ({len(plan.selection_dates)} complete states)
- Rolling folds: {len(plan.folds)}
- Consumed audit: {plan.audit_dates[0]} to {plan.audit_dates[-1]} ({len(plan.audit_dates)} complete states)
- Calibration candidates: none, expanding bias correction, expanding affine shrinkage
- Decision architectures: direct eight-state, family-first, family-first with interval abstention
- The source normalization, weights, sensitive thresholds, and independent-normal uncertainty are fixed from v0.3.1.
- The consumed audit is reported separately and has zero selection weight.

## Stability leaderboard

{_markdown(stability, ['stability_rank', 'candidate_id', 'stability_score', 'median_fold_rank', 'worst_fold_rank', 'leading_third_rate', 'baseline_dominance_rate', 'mean_macro_f1', 'mean_balanced_accuracy', 'mean_family_macro_f1', 'mean_transition_recall', 'mean_false_transition_rate', 'mean_abstention_rate', 'bootstrap_margin_lower', 'audit_rank', 'governance_pass'])}

## Research leader

- Candidate: `{selected['candidate_id']}`
- Calibration: `{selected['calibration_method']}`
- Architecture: `{selected['architecture_id']}`
- Stability score: {float(selected['stability_score']):.2f}
- Consumed-audit rank: {int(selected['audit_rank'])}
- Governance gate: {'pass' if bool(selected['governance_pass']) else 'fail'}

### Gate failures

{failures}

## Research leader by fold

{_markdown(selected_folds, ['fold_id', 'evaluation_start', 'evaluation_end', 'fold_rank', 'fold_score', 'dimension_rmse', 'growth_bias', 'inflation_bias', 'labour_bias', 'exact_regime_accuracy', 'balanced_accuracy', 'macro_f1', 'family_accuracy', 'family_balanced_accuracy', 'family_macro_f1', 'transition_recall', 'false_transition_rate', 'baseline_margin', 'abstention_rate', 'regime_collapse'])}

## Calibration diagnostics

{_markdown(calibration_summary, ['dimension', 'mean_pre_bias', 'mean_post_bias', 'mean_alpha', 'mean_beta'])}

## Per-regime performance — causally expanding selection path

{_markdown(selected_regimes, ['regime', 'support', 'forecast_count', 'precision', 'recall', 'f1'])}

## Transition events — causally expanding selection path

{_markdown(selected_transitions, ['event_type', 'actual_date', 'actual_from_regime', 'actual_to_regime', 'predicted_date', 'predicted_from_regime', 'predicted_to_regime', 'matched', 'lead_lag_months'])}

## Interpretation rules

This release is intentionally a small, pre-specified diagnostic rather than a
new broad tournament. A hierarchical or calibrated variant can advance only if
it improves balanced regime metrics, retains transition recall, avoids regime
collapse, beats the strongest naive baseline in most folds, and has a strictly
positive block-bootstrap lower margin. The consumed audit cannot be used to
retune or replace the selection leader.
"""
    report_path = prefix.with_suffix(".md")
    report_path.write_text(report, encoding="utf-8")
    return report_path, paths


def run_macro_state_hierarchical_diagnostics(
    repository: MacroRepository | None = None,
    stability_id: str | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    source, core, monthly = source_candidate_monthly(
        repository, config, stability_id
    )
    plan = temporal_plan(monthly["state_date"], config)
    diagnostics = run_hierarchical_diagnostics(
        monthly, plan, core, config
    )
    stability = diagnostics["stability"]
    selected = stability.iloc[0]
    selected_id = str(selected["candidate_id"])
    selected_candidate = next(
        item
        for item in build_hierarchical_candidates(config)
        if item["candidate_id"] == selected_id
    )
    gate_failures = governance_failures(selected, config)

    selected_expanding, selected_expanding_calibration = (
        expanding_candidate_frame(
            monthly,
            evaluation_dates=plan.selection_dates,
            candidate=selected_candidate,
            thresholds=core["thresholds"],
            config=config,
        )
    )
    selected_regimes = per_regime_metrics(
        selected_expanding, selected_expanding["state_date"]
    )
    selected_confusion = confusion_table(
        selected_expanding, selected_expanding["state_date"]
    )
    selected_transitions = transition_events(
        selected_expanding,
        selected_expanding["state_date"],
        int(
            config["hierarchical_diagnostics"][
                "transition_matching_window_months"
            ]
        ),
    )

    diagnostic_id = str(uuid.uuid4())
    report_path, output_paths = _write_outputs(
        diagnostic_id=diagnostic_id,
        identity=identity,
        source=source,
        plan=plan,
        selected=selected,
        gate_failures=gate_failures,
        stability=stability,
        fold_metrics=diagnostics["fold_metrics"],
        calibration_metrics=diagnostics["calibration_metrics"],
        audit=diagnostics["audit"],
        selected_regimes=selected_regimes,
        selected_confusion=selected_confusion,
        selected_transitions=selected_transitions,
        selected_expanding=selected_expanding,
        selected_expanding_calibration=selected_expanding_calibration,
    )
    warnings = []
    if not source.governance_pass:
        warnings.append(
            "The v0.3.1 source candidate failed its promotion gates."
        )
    if not bool(selected["governance_pass"]):
        warnings.append(
            "The hierarchical research leader fails one or more candidate gates."
        )
    metadata_path = report_path.with_name(
        report_path.stem + "_metadata.json"
    )
    metadata_path.write_text(
        json.dumps(
            {
                "diagnostic_id": diagnostic_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "source_stability_id": source.stability_id,
                "source_candidate_id": source.candidate_id,
                "selected_candidate_id": selected_id,
                "selected_calibration_method": selected["calibration_method"],
                "selected_architecture_id": selected["architecture_id"],
                "selected_governance_pass": bool(
                    selected["governance_pass"]
                ),
                "gate_failures": gate_failures,
                "warnings": warnings,
                "report_path": str(report_path),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    output_paths["metadata"] = metadata_path
    return {
        "diagnostic_id": diagnostic_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source": source,
        "core_candidate": core,
        "plan": plan,
        "candidate_count": len(build_hierarchical_candidates(config)),
        "selected_candidate_id": selected_id,
        "selected_calibration_method": str(
            selected["calibration_method"]
        ),
        "selected_architecture_id": str(selected["architecture_id"]),
        "selected_stability_score": float(selected["stability_score"]),
        "selected_governance_pass": bool(selected["governance_pass"]),
        "selected_audit_rank": int(selected["audit_rank"]),
        "gate_failures": gate_failures,
        "warnings": warnings,
        "stability": stability,
        "selected_fold_metrics": diagnostics["fold_metrics"].loc[
            diagnostics["fold_metrics"]["candidate_id"] == selected_id
        ].sort_values("fold_id"),
        "audit": diagnostics["audit"],
        "calibration_metrics": diagnostics["calibration_metrics"],
        "selected_regime_metrics": selected_regimes,
        "selected_transition_events": selected_transitions,
        "report_path": report_path,
        "output_paths": output_paths,
    }

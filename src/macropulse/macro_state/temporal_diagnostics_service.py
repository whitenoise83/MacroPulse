from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.temporal_diagnostics import (
    confusion_table,
    per_regime_metrics,
    run_temporal_policy_diagnostics,
    source_candidate_monthly,
    target_decomposition,
    temporal_plan,
    transition_events,
)
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _gate_failures(selected: pd.Series, config: dict[str, Any]) -> list[str]:
    gate = config["temporal_diagnostics"]["governance"]
    failures: list[str] = []
    if float(selected["baseline_dominance_rate"]) < float(
        gate["minimum_baseline_dominance_rate"]
    ):
        failures.append("naive-baseline dominance rate is below the gate")
    if float(selected["mean_family_accuracy"]) < float(
        gate["minimum_family_accuracy"]
    ):
        failures.append("regime-family accuracy is below the gate")
    if float(selected["mean_transition_recall"]) < float(
        gate["minimum_transition_recall"]
    ):
        failures.append("transition recall is below the gate")
    if float(selected["mean_false_transition_rate"]) > float(
        gate["maximum_false_transition_rate"]
    ):
        failures.append("false-transition rate exceeds the gate")
    if float(selected["regime_collapse_fold_rate"]) > float(
        gate["maximum_regime_collapse_fold_rate"]
    ):
        failures.append("regime-collapse fold rate exceeds the gate")
    if float(selected["bootstrap_margin_lower"]) <= float(
        gate["minimum_bootstrap_margin_lower"]
    ):
        failures.append(
            "block-bootstrap margin versus the strongest naive baseline "
            "is not strictly positive"
        )
    return failures


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
    target_selection: pd.DataFrame,
    target_audit: pd.DataFrame,
    policy_stability: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    audit: pd.DataFrame,
    selected_regimes: pd.DataFrame,
    selected_confusion: pd.DataFrame,
    selected_events: pd.DataFrame,
) -> tuple[Path, dict[str, Path]]:
    report_dir = settings.project_root / "reports" / "macro_state_temporal"
    report_dir.mkdir(parents=True, exist_ok=True)
    prefix = report_dir / f"model1d_temporal_{diagnostic_id}"
    paths = {
        "policy_stability": prefix.with_name(prefix.name + "_policy_stability.csv"),
        "fold_metrics": prefix.with_name(prefix.name + "_fold_metrics.csv"),
        "audit": prefix.with_name(prefix.name + "_audit.csv"),
        "target_selection": prefix.with_name(prefix.name + "_target_selection.csv"),
        "target_audit": prefix.with_name(prefix.name + "_target_audit.csv"),
        "selected_regime_metrics": prefix.with_name(prefix.name + "_selected_regimes.csv"),
        "selected_confusion": prefix.with_name(prefix.name + "_selected_confusion.csv"),
        "selected_transitions": prefix.with_name(prefix.name + "_selected_transitions.csv"),
    }
    policy_stability.to_csv(paths["policy_stability"], index=False)
    fold_metrics.to_csv(paths["fold_metrics"], index=False)
    audit.to_csv(paths["audit"], index=False)
    target_selection.to_csv(paths["target_selection"], index=False)
    target_audit.to_csv(paths["target_audit"], index=False)
    selected_regimes.to_csv(paths["selected_regime_metrics"], index=False)
    selected_confusion.to_csv(paths["selected_confusion"], index=False)
    selected_events.to_csv(paths["selected_transitions"], index=False)

    failures = (
        "\n".join(f"- {item}" for item in gate_failures)
        if gate_failures
        else "- None"
    )
    selected_folds = fold_metrics.loc[
        fold_metrics["policy_id"] == selected["policy_id"]
    ].sort_values("fold_id")
    report = f"""# Model 1D v0.3.2 Regime-Target and Temporal-Decision Diagnostics

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
- Temporal policies: raw monthly, hysteresis thresholds, one-month confirmation, persistence-prior probability filter
- The consumed audit is reported separately and has zero selection weight.

## Source target decomposition — selection

{_markdown(target_selection, ['dimension', 'months', 'rmse', 'mae', 'bias', 'correlation', 'accuracy'])}

## Source target decomposition — consumed audit

{_markdown(target_audit, ['dimension', 'months', 'rmse', 'mae', 'bias', 'correlation', 'accuracy'])}

## Temporal policy stability leaderboard

{_markdown(policy_stability, ['stability_rank', 'policy_id', 'stability_score', 'median_fold_rank', 'baseline_dominance_rate', 'mean_exact_regime_accuracy', 'mean_family_accuracy', 'mean_transition_f1', 'mean_false_transition_rate', 'bootstrap_margin_lower', 'audit_rank', 'governance_pass'])}

## Research temporal leader

- Policy: `{selected['policy_id']}`
- Stability score: {float(selected['stability_score']):.2f}
- Consumed-audit rank: {int(selected['audit_rank'])}
- Governance gate: {'pass' if bool(selected['governance_pass']) else 'fail'}

### Gate failures

{failures}

## Selected policy by fold

{_markdown(selected_folds, ['fold_id', 'evaluation_start', 'evaluation_end', 'policy_rank', 'policy_score', 'exact_regime_accuracy', 'family_accuracy', 'stable_month_accuracy', 'transition_month_accuracy', 'transition_precision', 'transition_recall', 'transition_f1', 'false_transition_rate', 'strongest_baseline_accuracy', 'baseline_margin'])}

## Selected policy per-regime metrics — selection

{_markdown(selected_regimes, ['regime', 'support', 'forecast_count', 'precision', 'recall', 'f1'])}

## Selected policy transition events — selection

{_markdown(selected_events, ['event_type', 'actual_date', 'actual_from_regime', 'actual_to_regime', 'predicted_date', 'predicted_from_regime', 'predicted_to_regime', 'matched', 'lead_lag_months'])}

## Interpretation

This release diagnoses whether Model 1D's failure to beat persistence originates
in the continuous dimensions, the eight-regime target, or the temporal decision
layer. It does not retune normalization, weights, thresholds, or uncertainty.
The v0.3.1 source candidate failed promotion gates; no v0.3.2 policy can be
promoted directly from this diagnostic exercise.
"""
    report_path = prefix.with_suffix(".md")
    report_path.write_text(report, encoding="utf-8")
    return report_path, paths


def run_macro_state_temporal_diagnostics(
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
    diagnostics = run_temporal_policy_diagnostics(monthly, plan, config)
    policy_stability = diagnostics["policy_stability"]
    fold_metrics = diagnostics["fold_metrics"]
    audit = diagnostics["audit"]
    selected = policy_stability.iloc[0]
    selected_policy = str(selected["policy_id"])
    selected_frame = diagnostics["policy_frames"][selected_policy]
    gate_failures = _gate_failures(selected, config)

    target_selection = target_decomposition(monthly, plan.selection_dates)
    target_audit = target_decomposition(monthly, plan.audit_dates)
    selected_regimes = per_regime_metrics(
        selected_frame, plan.selection_dates
    )
    selected_confusion = confusion_table(
        selected_frame, plan.selection_dates
    )
    selected_events = transition_events(
        selected_frame,
        plan.selection_dates,
        int(config["temporal_diagnostics"]["transition_matching_window_months"]),
    )

    diagnostic_id = str(uuid.uuid4())
    report_path, output_paths = _write_outputs(
        diagnostic_id=diagnostic_id,
        identity=identity,
        source=source,
        plan=plan,
        selected=selected,
        gate_failures=gate_failures,
        target_selection=target_selection,
        target_audit=target_audit,
        policy_stability=policy_stability,
        fold_metrics=fold_metrics,
        audit=audit,
        selected_regimes=selected_regimes,
        selected_confusion=selected_confusion,
        selected_events=selected_events,
    )
    warnings = []
    if not source.governance_pass:
        warnings.append(
            "The v0.3.1 source candidate failed its promotion gates."
        )
    if not bool(selected["governance_pass"]):
        warnings.append(
            "The temporal research leader fails one or more candidate gates."
        )
    metadata_path = report_path.with_name(report_path.stem + "_metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "diagnostic_id": diagnostic_id,
                "model_id": identity.model_id,
                "model_version": identity.model_version,
                "source_stability_id": source.stability_id,
                "source_candidate_id": source.candidate_id,
                "selected_policy_id": selected_policy,
                "selected_governance_pass": bool(selected["governance_pass"]),
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
        "selected_policy_id": selected_policy,
        "selected_stability_score": float(selected["stability_score"]),
        "selected_governance_pass": bool(selected["governance_pass"]),
        "selected_audit_rank": int(selected["audit_rank"]),
        "gate_failures": gate_failures,
        "warnings": warnings,
        "target_selection": target_selection,
        "target_audit": target_audit,
        "policy_stability": policy_stability,
        "selected_fold_metrics": fold_metrics.loc[
            fold_metrics["policy_id"] == selected_policy
        ].sort_values("fold_id"),
        "audit": audit,
        "selected_regime_metrics": selected_regimes,
        "selected_transition_events": selected_events,
        "report_path": report_path,
        "output_paths": output_paths,
    }

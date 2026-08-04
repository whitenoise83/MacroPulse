from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.fixed_horizon_probabilistic import (
    run_fixed_horizon_probabilistic_audit,
)
from macropulse.macro_state.realtime_soft_targets import (
    build_mode_monthlies,
    build_soft_targets,
    reconstruct_actual_vintages,
)
from macropulse.macro_state.temporal_diagnostics import (
    source_candidate_monthly,
    temporal_plan,
)
from macropulse.macro_state.tournament import load_tournament_dataset
from macropulse.macro_state.versioning import (
    current_macro_state_identity,
    load_macro_state_governance,
)
from macropulse.settings import settings


def _markdown(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "_No rows._"
    available = [column for column in columns if column in frame.columns]
    return frame[available].to_markdown(index=False)


def _write_outputs(
    *,
    audit_id: str,
    identity: Any,
    source: Any,
    plan: Any,
    result: dict[str, Any],
) -> tuple[Path, dict[str, Path]]:
    output_dir = (
        settings.project_root
        / "reports"
        / "macro_state_fixed_horizon_probabilistic"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"model1d_fixed_horizon_{audit_id}"
    frames = {
        "target_lock": result["target_lock"],
        "state_availability": result["state_availability"],
        "missing_evidence": result["missing_evidence"],
        "locked_targets": result["locked_targets"],
        "benchmark_predictions": result["benchmark_predictions"],
        "benchmark_fold_metrics": result["benchmark_fold_metrics"],
        "fold_comparisons": result["fold_comparisons"],
        "benchmark_summary": result["benchmark_summary"],
        "reliability": result["reliability"],
        "prospective_shadow": result["prospective_shadow"],
        "governance_flags": result["governance_flags"],
    }
    output_paths: dict[str, Path] = {}
    for name, frame in frames.items():
        path = Path(f"{prefix}_{name}.csv")
        frame.to_csv(path, index=False)
        output_paths[name] = path

    metadata = {
        "audit_id": audit_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source_stability_id": source.stability_id,
        "source_candidate_id": source.candidate_id,
        "source_core_candidate_id": source.core_candidate_id,
        "source_candidate_governance_pass": bool(source.governance_pass),
        "selection_start": str(plan.selection_dates[0]),
        "selection_end": str(plan.selection_dates[-1]),
        "selection_months": len(plan.selection_dates),
        "consumed_audit_start": str(plan.audit_dates[0]),
        "consumed_audit_end": str(plan.audit_dates[-1]),
        "consumed_audit_months": len(plan.audit_dates),
        "rolling_folds": len(plan.folds),
        "bootstrap": result["bootstrap"],
        "fixed_horizon_governance_pass": bool(
            result["fixed_horizon_governance_pass"]
        ),
        "status": "diagnostic_research_evidence_only",
    }
    metadata_path = Path(f"{prefix}_metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    output_paths["metadata"] = metadata_path

    source_summary = result["benchmark_summary"].loc[
        result["benchmark_summary"]["benchmark_id"] == "source"
    ]
    if source_summary.empty:
        win_rate = float("nan")
        brier = float("nan")
        macro_f1 = float("nan")
        ece = float("nan")
    else:
        row = source_summary.iloc[0]
        win_rate = float(row["reference_win_rate"])
        brier = float(row["mean_soft_brier"])
        macro_f1 = float(row["mean_family_macro_f1"])
        ece = float(row["mean_expected_calibration_error"])

    report = f"""# Model 1D v0.3.6 Fixed-Horizon Target Lock and Probabilistic Benchmark Audit

## Status

- Audit ID: `{audit_id}`
- Model: `{identity.model_id}` v{identity.model_version} (`development`)
- Source stability ID: `{source.stability_id}`
- Source candidate: `{source.candidate_id}`
- Source candidate v0.3.1 governance gate: `{'pass' if source.governance_pass else 'fail'}`
- Fixed-horizon governance result: `{'pass' if result['fixed_horizon_governance_pass'] else 'fail'}`
- Selection period: {plan.selection_dates[0]} to {plan.selection_dates[-1]} ({len(plan.selection_dates)} months)
- Consumed audit period: {plan.audit_dates[0]} to {plan.audit_dates[-1]} ({len(plan.audit_dates)} months)

This is research evidence only. It does not approve a Model 1D candidate and does not reopen the consumed audit for tuning.

## Target lock

{_markdown(result['target_lock'], ['primary_target_mode', 'primary_target_level', 'secondary_target_level', 'governance_reference', 'latest_revised_substitution_allowed', 'complete_states', 'expected_states', 'missing_states'])}

The five-family fixed-90-day target is the locked primary research target. Latest-revised observations are not permitted as substitutes for missing fixed-horizon evidence. The eight-state subtype remains report-only.

## Fixed-horizon state availability

{_markdown(result['state_availability'], ['state_date', 'expected_targets', 'available_targets', 'complete_state', 'state_available_date', 'latest_actual_as_of_date'])}

## Missing fixed-horizon evidence

{_markdown(result['missing_evidence'], ['state_date', 'source_target', 'target_period', 'availability_status', 'requested_evaluation_date', 'actual_as_of_date', 'snapshot_gap_days'])}

## Probabilistic benchmark design

The frozen source probabilities are compared with five causal benchmarks:

1. hard persistence;
2. prior soft-target persistence;
3. Dirichlet-smoothed persistence;
4. first-order Markov probabilities;
5. rolling empirical family frequencies.

Each benchmark uses only target states whose fixed-horizon evidence was available by the forecast month.

## Rolling benchmark summary

{_markdown(result['benchmark_summary'], ['soft_brier_rank', 'benchmark_id', 'folds', 'mean_family_accuracy', 'mean_family_balanced_accuracy', 'mean_family_macro_f1', 'mean_soft_brier', 'mean_soft_log_loss', 'mean_top2_coverage', 'mean_confidence_weighted_accuracy', 'mean_expected_calibration_error', 'reference_win_rate', 'mean_weighted_accuracy_margin', 'mean_macro_f1_margin', 'mean_soft_brier_improvement'])}

The source records mean family macro-F1 {macro_f1:.3f}, mean soft Brier score {brier:.3f}, expected calibration error {ece:.3f}, and a fold win rate of {win_rate:.1%} against the pre-specified soft-persistence reference.

## Brier decomposition diagnostics

{_markdown(result['benchmark_summary'], ['benchmark_id', 'mean_hard_brier', 'mean_brier_reliability', 'mean_brier_resolution', 'mean_brier_uncertainty'])}

## Fold comparisons with the governance reference

{_markdown(result['fold_comparisons'], ['fold_id', 'reference_benchmark', 'source_weighted_accuracy', 'reference_weighted_accuracy', 'weighted_accuracy_margin', 'source_beats_reference', 'source_macro_f1', 'reference_macro_f1', 'macro_f1_margin', 'source_soft_brier', 'reference_soft_brier', 'soft_brier_improvement', 'source_ece', 'reference_ece', 'source_brier_rank'])}

## Bootstrap margin versus soft persistence

- Mean confidence-weighted monthly margin: {result['bootstrap']['bootstrap_margin_mean']:.4f}
- Lower confidence bound: {result['bootstrap']['bootstrap_margin_lower']:.4f}
- Upper confidence bound: {result['bootstrap']['bootstrap_margin_upper']:.4f}

## Prospective shadow isolation

{_markdown(result['prospective_shadow'], ['prospective_shadow_start', 'available_shadow_months', 'first_shadow_month', 'last_shadow_month', 'selection_contains_shadow_month', 'consumed_audit_contains_shadow_month', 'prospective_isolation_pass'])}

## Governance checks

{_markdown(result['governance_flags'], ['check_id', 'passed', 'observed', 'threshold', 'interpretation'])}

## Decision rule

Model 1D cannot return to candidate consideration unless the fixed-horizon target remains complete without revised-value substitution, benchmark construction is availability-consistent, the source wins at least five of seven folds against soft persistence, the bootstrap lower margin is positive, macro-F1 is not reduced, and probability calibration remains acceptable.
"""
    report_path = Path(f"{prefix}.md")
    report_path.write_text(report, encoding="utf-8")
    return report_path, output_paths


def run_macro_state_fixed_horizon_probabilistic_audit(
    repository: MacroRepository | None = None,
    stability_id: str | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    source, core, source_monthly = source_candidate_monthly(
        repository, config, stability_id
    )
    reconstruction_id, dataset = load_tournament_dataset(
        repository, source.reconstruction_id
    )
    if reconstruction_id != source.reconstruction_id:
        raise RuntimeError("Source and target reconstruction lineage do not match.")
    actual_vintages = reconstruct_actual_vintages(repository, dataset, config)
    mode_monthlies = build_mode_monthlies(
        dataset, actual_vintages, source_monthly, core, config
    )
    soft_targets = build_soft_targets(mode_monthlies, config)
    plan = temporal_plan(source_monthly["state_date"], config)
    result = run_fixed_horizon_probabilistic_audit(
        actual_vintages=actual_vintages,
        soft_targets=soft_targets,
        source_monthly=source_monthly,
        plan=plan,
        config=config,
    )
    audit_id = str(uuid.uuid4())
    report_path, output_paths = _write_outputs(
        audit_id=audit_id,
        identity=identity,
        source=source,
        plan=plan,
        result=result,
    )
    warnings = [
        "The v0.3.1 source candidate failed its promotion gates.",
        "The 2024-08 to 2026-03 audit is consumed and remains report-only.",
    ]
    if not result["fixed_horizon_governance_pass"]:
        warnings.append(
            "The fixed-horizon probabilistic benchmark architecture fails one or more governance checks."
        )
    return {
        "audit_id": audit_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source": source,
        "plan": plan,
        **result,
        "report_path": report_path,
        "output_paths": output_paths,
        "warnings": warnings,
    }

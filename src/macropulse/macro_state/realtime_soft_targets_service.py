from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.realtime_soft_targets import (
    reconstruct_actual_vintages,
    run_realtime_soft_target_audit,
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
    return frame[columns].to_markdown(index=False)


def _write_outputs(
    *,
    audit_id: str,
    identity: Any,
    source: Any,
    plan: Any,
    actual_vintages: pd.DataFrame,
    result: dict[str, Any],
) -> tuple[Path, dict[str, Path]]:
    output_dir = settings.project_root / "reports" / "macro_state_realtime_targets"
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"model1d_realtime_targets_{audit_id}"
    frames = {
        "actual_vintages": actual_vintages,
        "mode_completeness": result["mode_completeness"],
        "vintage_agreement": result["vintage_agreement"],
        "mode_monthly": result["mode_monthly"],
        "soft_targets": result["soft_targets"],
        "benchmark_fold_metrics": result["benchmark_fold_metrics"],
        "fold_comparisons": result["fold_comparisons"],
        "benchmark_summary": result["benchmark_summary"],
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
        "soft_target_governance_pass": bool(
            result["soft_target_governance_pass"]
        ),
        "status": "diagnostic_research_evidence_only",
    }
    metadata_path = Path(f"{prefix}_metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    output_paths["metadata"] = metadata_path

    initial_summary = result["benchmark_summary"].loc[
        (result["benchmark_summary"]["target_mode"] == "initial_release")
        & (result["benchmark_summary"]["benchmark_id"] == "source")
    ]
    if initial_summary.empty:
        source_win_rate = float("nan")
        source_macro_f1 = float("nan")
        source_brier = float("nan")
    else:
        source_row = initial_summary.iloc[0]
        source_win_rate = float(source_row["baseline_win_rate"])
        source_macro_f1 = float(source_row["mean_family_macro_f1"])
        source_brier = float(source_row["mean_soft_brier"])

    report = f"""# Model 1D v0.3.5 Real-Time Target Reconstruction and Soft-Label Audit

## Status

- Audit ID: `{audit_id}`
- Model: `{identity.model_id}` v{identity.model_version} (`development`)
- Source stability ID: `{source.stability_id}`
- Source candidate: `{source.candidate_id}`
- Source candidate v0.3.1 governance gate: `{'pass' if source.governance_pass else 'fail'}`
- Soft-target governance result: `{'pass' if result['soft_target_governance_pass'] else 'fail'}`
- Selection period: {plan.selection_dates[0]} to {plan.selection_dates[-1]} ({len(plan.selection_dates)} months)
- Consumed audit period: {plan.audit_dates[0]} to {plan.audit_dates[-1]} ({len(plan.audit_dates)} months)

This is research evidence only. It does not approve a Model 1D candidate or release the consumed audit for tuning.

## Actual-vintage reconstruction completeness

{_markdown(result['mode_completeness'], ['target_mode', 'expected_target_rows', 'available_target_rows', 'target_row_completeness', 'expected_states', 'complete_states', 'complete_state_share'])}

`initial_release` uses the actual outcomes recorded by the approved source pseudo-real-time backtests. `fixed_horizon_90d` uses the latest cached historical snapshot no later than target-period end plus 90 days. `latest_revised` uses the locally stored latest observation vintage. The audit makes no network request.

## Cross-vintage target agreement

{_markdown(result['vintage_agreement'], ['left_mode', 'right_mode', 'common_months', 'hard_family_agreement', 'hard_regime_agreement', 'soft_primary_family_agreement', 'growth_score_mae', 'inflation_score_mae', 'labour_score_mae'])}

## Soft-label design

The five-family state is the primary target. The eight-state regime is retained as a secondary subtype. Each actual month is evaluated under the pre-specified threshold set and a deterministic ±0.10 score perturbation grid. The resulting family frequencies form the soft target distribution. A month is marked ambiguous when the top family probability or the probability margin is below the governance floor.

## Rolling benchmark summary

{_markdown(result['benchmark_summary'], ['target_mode', 'benchmark_id', 'folds', 'mean_family_accuracy', 'mean_family_balanced_accuracy', 'mean_family_macro_f1', 'mean_soft_brier', 'mean_soft_log_loss', 'mean_top2_coverage', 'mean_confidence_weighted_accuracy', 'baseline_win_rate', 'mean_baseline_margin'])}

For the initial-release target, the source has rolling mean family macro-F1 {source_macro_f1:.3f}, mean soft Brier score {source_brier:.3f}, and a persistence win rate of {source_win_rate:.1%}.

## Bootstrap margin versus persistence

- Mean confidence-weighted monthly margin: {result['bootstrap']['bootstrap_margin_mean']:.4f}
- Lower confidence bound: {result['bootstrap']['bootstrap_margin_lower']:.4f}
- Upper confidence bound: {result['bootstrap']['bootstrap_margin_upper']:.4f}

## Prospective shadow isolation

{_markdown(result['prospective_shadow'], ['prospective_shadow_start', 'available_shadow_months', 'first_shadow_month', 'last_shadow_month', 'selection_contains_shadow_month', 'consumed_audit_contains_shadow_month', 'prospective_isolation_pass'])}

## Governance checks

{_markdown(result['governance_flags'], ['check_id', 'passed', 'observed', 'threshold', 'interpretation'])}

## Decision

Model 1D should not return to candidate selection unless the real-time target reconstruction is sufficiently complete, the soft five-family target is stable across vintages, and the source forecast beats persistence with a strictly positive bootstrap lower margin. Months beginning with the prospective shadow date remain external evidence only.
"""
    report_path = Path(f"{prefix}.md")
    report_path.write_text(report, encoding="utf-8")
    return report_path, output_paths


def run_macro_state_realtime_soft_target_audit(
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
    plan = temporal_plan(source_monthly["state_date"], config)
    audit = run_realtime_soft_target_audit(
        dataset=dataset,
        actual_vintages=actual_vintages,
        source_monthly=source_monthly,
        core_candidate=core,
        plan=plan,
        config=config,
    )
    audit_id = str(uuid.uuid4())
    report_path, output_paths = _write_outputs(
        audit_id=audit_id,
        identity=identity,
        source=source,
        plan=plan,
        actual_vintages=actual_vintages,
        result=audit,
    )
    warnings = [
        "The v0.3.1 source candidate failed its promotion gates.",
        "The 2024-08 to 2026-03 audit is consumed and remains report-only.",
    ]
    if not audit["soft_target_governance_pass"]:
        warnings.append(
            "The real-time soft-target architecture fails one or more governance checks."
        )
    return {
        "audit_id": audit_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source": source,
        "plan": plan,
        "actual_vintages": actual_vintages,
        **audit,
        "report_path": report_path,
        "output_paths": output_paths,
        "warnings": warnings,
    }

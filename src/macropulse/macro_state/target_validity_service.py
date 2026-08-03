from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.target_validity import run_target_validity_audit
from macropulse.macro_state.temporal_diagnostics import source_candidate_monthly, temporal_plan
from macropulse.macro_state.versioning import current_macro_state_identity, load_macro_state_governance
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
    result: dict[str, Any],
) -> tuple[Path, dict[str, Path]]:
    output_dir = settings.project_root / "reports" / "macro_state_target_validity"
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / f"model1d_target_validity_{audit_id}"

    output_frames = {
        "lineage": result["lineage"],
        "label_stability": result["label_stability"],
        "threshold_sensitivity": result["threshold_sensitivity"],
        "occupancy": result["occupancy"],
        "benchmark_fold_metrics": result["benchmark_fold_metrics"],
        "benchmark_summary": result["benchmark_summary"],
        "audit_benchmarks": result["audit_benchmarks"],
        "economic_separation": result["economic_separation"],
        "validity_flags": result["validity_flags"],
    }
    output_paths: dict[str, Path] = {}
    for name, frame in output_frames.items():
        path = Path(f"{prefix}_{name}.csv")
        frame.to_csv(path, index=False)
        output_paths[name] = path

    metadata = {
        "audit_id": audit_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source_stability_id": source.stability_id,
        "source_candidate_id": source.candidate_id,
        "source_candidate_governance_pass": bool(source.governance_pass),
        "selection_start": str(plan.selection_dates[0]),
        "selection_end": str(plan.selection_dates[-1]),
        "selection_months": len(plan.selection_dates),
        "audit_start": str(plan.audit_dates[0]),
        "audit_end": str(plan.audit_dates[-1]),
        "audit_months": len(plan.audit_dates),
        "rolling_folds": len(plan.folds),
        "target_validity_pass": bool(result["target_validity_pass"]),
        "status": "diagnostic_research_evidence_only",
    }
    metadata_path = Path(f"{prefix}_metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    output_paths["metadata"] = metadata_path

    flags = result["validity_flags"]
    benchmark = result["benchmark_summary"]
    source_benchmark = benchmark.loc[benchmark["benchmark_id"] == "source_direct"].iloc[0]
    occupancy = result["occupancy"]
    regime_occupancy = occupancy.loc[occupancy["target_level"] == "eight_state"]
    stability = result["label_stability"]
    report = f"""# Model 1D v0.3.4 Target-Definition and Benchmark-Validity Audit

## Status

- Audit ID: `{audit_id}`
- Model: `{identity.model_id}` v{identity.model_version} (`development`)
- Source stability ID: `{source.stability_id}`
- Source candidate: `{source.candidate_id}`
- Source candidate v0.3.1 governance gate: `{'pass' if source.governance_pass else 'fail'}`
- Target-validity audit: `{'pass' if result['target_validity_pass'] else 'fail'}`
- Selection period: {plan.selection_dates[0]} to {plan.selection_dates[-1]} ({len(plan.selection_dates)} months)
- Consumed audit period: {plan.audit_dates[0]} to {plan.audit_dates[-1]} ({len(plan.audit_dates)} months)

This is diagnostic research evidence only. It does not approve a Model 1D candidate or alter the consumed-audit status.

## Validity checks

{_markdown(flags, ['check_id', 'passed', 'observed', 'threshold', 'interpretation'])}

## Construction and vintage lineage

{_markdown(result['lineage'], ['source_target', 'rows', 'states', 'information_cutoff_after_state', 'data_as_of_after_state', 'max_observation_after_cutoff', 'target_leakage_rows', 'future_target_period_rows', 'missing_actual_release_date_rows', 'actual_revision_vintage_recorded', 'evaluation_target_mode'])}

The forecast lineage can pass no-look-ahead checks while the realised target remains ex-post. The current backtest actuals do not carry an explicit revision-vintage timestamp, so this audit does not treat the realised eight-state label as a proven real-time target.

## Label stability summary

- Mean eight-state boundary distance (L-infinity): {stability['regime_boundary_distance_linf'].mean():.3f}
- Median eight-state boundary distance (L-infinity): {stability['regime_boundary_distance_linf'].median():.3f}
- Mean family boundary distance (L-infinity): {stability['family_boundary_distance_linf'].mean():.3f}
- Threshold-consensus share: {stability['threshold_consensus'].mean():.1%}

## Realised occupancy

{_markdown(regime_occupancy, ['label', 'count', 'share', 'median_run_months', 'maximum_run_months'])}

## Rolling benchmark summary

{_markdown(benchmark, ['benchmark_id', 'folds', 'mean_exact_regime_accuracy', 'mean_balanced_accuracy', 'mean_macro_f1', 'mean_family_accuracy', 'mean_family_macro_f1', 'mean_transition_recall', 'mean_false_transition_rate', 'mean_baseline_margin', 'baseline_win_rate'])}

The source direct classifier has mean exact accuracy {source_benchmark['mean_exact_regime_accuracy']:.1%}, mean macro-F1 {source_benchmark['mean_macro_f1']:.3f}, and a rolling-fold win rate of {source_benchmark['baseline_win_rate']:.1%} against the strongest naive benchmark.

## Consumed-audit benchmarks

{_markdown(result['audit_benchmarks'], ['audit_rank', 'benchmark_id', 'exact_regime_accuracy', 'balanced_accuracy', 'macro_f1', 'family_accuracy', 'family_macro_f1', 'transition_recall', 'false_transition_rate', 'strongest_naive_benchmark', 'baseline_margin'])}

The consumed audit is reported for external evidence only and is not used to tune the target definition or select a benchmark.

## Economic separation

{_markdown(result['economic_separation'], ['horizon_months', 'dimension', 'target_level', 'outcome_type', 'observations', 'groups_observed', 'minimum_group_support', 'maximum_group_share', 'eta_squared'])}

## Decision

The eight-state target should not advance to another candidate tournament unless the failed validity checks are resolved. In particular, real-time target vintages, label robustness, minimum regime support, benchmark dominance, and incremental economic separation beyond the five-family target require explicit evidence.
"""
    report_path = Path(f"{prefix}.md")
    report_path.write_text(report, encoding="utf-8")
    return report_path, output_paths


def run_macro_state_target_validity_audit(
    repository: MacroRepository | None = None,
    stability_id: str | None = None,
) -> dict[str, Any]:
    repository = repository or MacroRepository()
    repository.initialise()
    config = load_macro_state_governance()
    identity = current_macro_state_identity()
    source, core, monthly = source_candidate_monthly(repository, config, stability_id)
    plan = temporal_plan(monthly["state_date"], config)
    lineage_inputs = repository.query_df(
        """
        SELECT *
        FROM macro_state_history_inputs
        WHERE reconstruction_id = ?
        ORDER BY state_date, source_target
        """,
        [source.reconstruction_id],
    )
    if lineage_inputs.empty:
        raise RuntimeError(
            f"Reconstruction {source.reconstruction_id} has no lineage inputs."
        )
    audit = run_target_validity_audit(monthly, plan, core, lineage_inputs, config)
    audit_id = str(uuid.uuid4())
    report_path, output_paths = _write_outputs(
        audit_id=audit_id,
        identity=identity,
        source=source,
        plan=plan,
        result=audit,
    )
    return {
        "audit_id": audit_id,
        "model_id": identity.model_id,
        "model_version": identity.model_version,
        "source": source,
        "plan": plan,
        **audit,
        "report_path": report_path,
        "output_paths": output_paths,
        "warnings": [
            "The v0.3.1 source candidate failed its promotion gates."
        ]
        + (
            []
            if audit["target_validity_pass"]
            else [
                "The realised target fails one or more target-validity checks.",
                "The consumed audit remains report-only and must not be used for tuning.",
            ]
        ),
    }

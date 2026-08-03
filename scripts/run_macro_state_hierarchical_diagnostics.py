from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.hierarchical_diagnostics_service import (
    run_macro_state_hierarchical_diagnostics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D causal dimension calibration and hierarchical "
            "regime diagnostics."
        )
    )
    parser.add_argument(
        "--stability-id",
        help="Optional successful Model 1D v0.3.1 stability run ID.",
    )
    args = parser.parse_args()
    result = run_macro_state_hierarchical_diagnostics(
        repository=MacroRepository(),
        stability_id=args.stability_id,
    )

    source = result["source"]
    plan = result["plan"]
    print("Model 1D causal calibration and hierarchical diagnostics complete")
    print(f"Diagnostic ID: {result['diagnostic_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        "(development)"
    )
    print(f"Source stability ID: {source.stability_id}")
    print(f"Source candidate: {source.candidate_id}")
    print(
        f"Source candidate v0.3.1 gate: "
        f"{'pass' if source.governance_pass else 'fail'}"
    )
    print(
        f"Selection sample: {plan.selection_dates[0]} to "
        f"{plan.selection_dates[-1]} ({len(plan.selection_dates)} complete states)"
    )
    print(
        f"Consumed audit sample: {plan.audit_dates[0]} to "
        f"{plan.audit_dates[-1]} ({len(plan.audit_dates)} complete states)"
    )
    print(f"Rolling folds: {len(plan.folds)}")
    print(f"Candidates evaluated: {result['candidate_count']}")
    print()
    print("Research hierarchical leader")
    print(f"  Candidate: {result['selected_candidate_id']}")
    print(f"  Calibration: {result['selected_calibration_method']}")
    print(f"  Architecture: {result['selected_architecture_id']}")
    print(f"  Stability score: {result['selected_stability_score']:.2f}")
    print(f"  Consumed-audit rank: {result['selected_audit_rank']}")
    print(
        f"  Candidate governance gate: "
        f"{'pass' if result['selected_governance_pass'] else 'fail'}"
    )
    if result["gate_failures"]:
        print()
        print("Gate failures")
        for failure in result["gate_failures"]:
            print(f"- {failure}")
    if result["warnings"]:
        print()
        print("Governance warnings")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print()
    print("Top hierarchical candidates")
    columns = [
        "stability_rank",
        "candidate_id",
        "stability_score",
        "median_fold_rank",
        "worst_fold_rank",
        "leading_third_rate",
        "baseline_dominance_rate",
        "mean_macro_f1",
        "mean_balanced_accuracy",
        "mean_family_macro_f1",
        "mean_transition_recall",
        "mean_false_transition_rate",
        "mean_abstention_rate",
        "bootstrap_margin_lower",
        "audit_rank",
        "governance_pass",
    ]
    print(result["stability"][columns].head(12).to_string(index=False))
    print()
    print("Selected candidate fold results")
    fold_columns = [
        "fold_id",
        "evaluation_start",
        "evaluation_end",
        "fold_rank",
        "fold_score",
        "dimension_rmse",
        "growth_bias",
        "inflation_bias",
        "labour_bias",
        "exact_regime_accuracy",
        "balanced_accuracy",
        "macro_f1",
        "family_accuracy",
        "family_macro_f1",
        "transition_recall",
        "false_transition_rate",
        "baseline_margin",
        "abstention_rate",
    ]
    print(result["selected_fold_metrics"][fold_columns].to_string(index=False))
    print()
    print("Selected candidate per-regime metrics")
    print(result["selected_regime_metrics"].to_string(index=False))
    print()
    print(f"Report: {result['report_path']}")
    print("Output files")
    for name, path in result["output_paths"].items():
        print(f"  {name}: {path}")
    print(
        "Status: diagnostic research evidence only; not candidate or "
        "production approved."
    )


if __name__ == "__main__":
    main()

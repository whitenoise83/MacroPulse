from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.temporal_diagnostics_service import (
    run_macro_state_temporal_diagnostics,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D v0.3.2 regime-target and temporal-decision "
            "diagnostics using the latest v0.3.1 research stability leader."
        )
    )
    parser.add_argument(
        "--stability-id",
        help=(
            "Source stability ID. Defaults to the latest successful "
            "rolling-origin run."
        ),
    )
    args = parser.parse_args()
    result = run_macro_state_temporal_diagnostics(
        repository=MacroRepository(),
        stability_id=args.stability_id,
    )
    source = result["source"]
    plan = result["plan"]
    print("Model 1D regime-target and temporal-decision diagnostics complete")
    print(f"Diagnostic ID: {result['diagnostic_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        "(development)"
    )
    print(f"Source stability ID: {source.stability_id}")
    print(f"Source candidate: {source.candidate_id}")
    print(
        "Source candidate v0.3.1 gate: "
        f"{'pass' if source.governance_pass else 'fail'}"
    )
    print(
        "Selection sample: "
        f"{plan.selection_dates[0]} to {plan.selection_dates[-1]} "
        f"({len(plan.selection_dates)} complete states)"
    )
    print(
        "Consumed audit sample: "
        f"{plan.audit_dates[0]} to {plan.audit_dates[-1]} "
        f"({len(plan.audit_dates)} complete states)"
    )
    print(f"Rolling folds: {len(plan.folds)}")
    print()
    print("Research temporal leader")
    print(f"  Policy: {result['selected_policy_id']}")
    print(f"  Stability score: {result['selected_stability_score']:.2f}")
    print(f"  Consumed-audit rank: {result['selected_audit_rank']}")
    print(
        "  Candidate governance gate: "
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
    print("Source target decomposition — selection")
    print(
        result["target_selection"][[
            "dimension", "months", "rmse", "mae", "bias",
            "correlation", "accuracy",
        ]].to_string(index=False)
    )
    print()
    print("Temporal policy stability leaderboard")
    print(
        result["policy_stability"][[
            "stability_rank", "policy_id", "stability_score",
            "median_fold_rank", "baseline_dominance_rate",
            "mean_exact_regime_accuracy", "mean_family_accuracy",
            "mean_transition_f1", "mean_false_transition_rate",
            "bootstrap_margin_lower", "audit_rank", "governance_pass",
        ]].to_string(index=False)
    )
    print()
    print("Selected temporal policy by fold")
    print(
        result["selected_fold_metrics"][[
            "fold_id", "evaluation_start", "evaluation_end", "policy_rank",
            "policy_score", "exact_regime_accuracy", "family_accuracy",
            "stable_month_accuracy", "transition_month_accuracy",
            "transition_precision", "transition_recall", "transition_f1",
            "false_transition_rate", "strongest_baseline_accuracy",
            "baseline_margin",
        ]].to_string(index=False)
    )
    print()
    print("Selected policy per-regime metrics — selection")
    print(
        result["selected_regime_metrics"][[
            "regime", "support", "forecast_count", "precision", "recall", "f1",
        ]].to_string(index=False)
    )
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

from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.rolling_tournament_service import (
    run_macro_state_stability_tournament,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Model 1D v0.3.1 rolling-origin normalization, "
            "weighting, threshold, and uncertainty stability tournament."
        )
    )
    parser.add_argument(
        "--reconstruction-id",
        help=(
            "Production-vintage reconstruction ID. Defaults to the latest "
            "available reconstruction."
        ),
    )
    args = parser.parse_args()
    result = run_macro_state_stability_tournament(
        repository=MacroRepository(),
        reconstruction_id=args.reconstruction_id,
    )
    plan = result["plan"]
    print("Model 1D rolling-origin stability tournament complete")
    print(f"Stability ID: {result['stability_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} "
        "(development)"
    )
    print(f"Reconstruction ID: {result['reconstruction_id']}")
    print(f"Source v0.3 tournament ID: {result['source_tournament_id']}")
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
    for fold in plan.folds:
        print(
            f"  {fold.fold_id}: train {fold.training_dates[0]} to "
            f"{fold.training_dates[-1]} ({len(fold.training_dates)}), "
            f"evaluate {fold.evaluation_dates[0]} to "
            f"{fold.evaluation_dates[-1]} "
            f"({len(fold.evaluation_dates)})"
        )
    print(f"Core candidates evaluated: {result['core_candidates']}")
    print(f"Final candidates evaluated: {result['final_candidates']}")
    print()
    print("Research stability leader")
    print(f"  Candidate: {result['selected_candidate_id']}")
    print(f"  Core: {result['selected_core_candidate_id']}")
    print(f"  Uncertainty: {result['selected_uncertainty_id']}")
    print(f"  Stability score: {result['selected_stability_score']:.2f}")
    print(f"  Audit rank: {result['selected_audit_rank']}")
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
    print("Top rolling-origin candidates")
    print(
        result["final_stability"][
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
        ].head(15).to_string(index=False)
    )
    print()
    print("Selected candidate fold results")
    print(
        result["selected_fold_metrics"][
            [
                "fold_id",
                "evaluation_start",
                "evaluation_end",
                "final_rank",
                "final_score",
                "exact_regime_accuracy",
                "strongest_baseline_accuracy",
                "baseline_margin",
                "brier_score",
                "log_loss",
                "coverage_80",
                "uncertainty_method_rank",
            ]
        ].to_string(index=False)
    )
    print()
    print(f"Report: {result['report_path']}")
    print(
        "Status: rolling-origin research evidence only; not candidate or "
        "production approved."
    )


if __name__ == "__main__":
    main()

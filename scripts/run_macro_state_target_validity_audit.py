from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.target_validity_service import (
    run_macro_state_target_validity_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D target-definition, label-stability, benchmark-validity, "
            "and economic-separation diagnostics."
        )
    )
    parser.add_argument(
        "--stability-id",
        help="Optional successful Model 1D v0.3.1 stability run ID.",
    )
    args = parser.parse_args()
    result = run_macro_state_target_validity_audit(
        repository=MacroRepository(),
        stability_id=args.stability_id,
    )

    source = result["source"]
    plan = result["plan"]
    print("Model 1D target-definition and benchmark-validity audit complete")
    print(f"Audit ID: {result['audit_id']}")
    print(f"Model: {result['model_id']} v{result['model_version']} (development)")
    print(f"Source stability ID: {source.stability_id}")
    print(f"Source candidate: {source.candidate_id}")
    print(
        "Source candidate v0.3.1 gate: "
        f"{'pass' if source.governance_pass else 'fail'}"
    )
    print(
        f"Selection sample: {plan.selection_dates[0]} to {plan.selection_dates[-1]} "
        f"({len(plan.selection_dates)} complete states)"
    )
    print(
        f"Consumed audit sample: {plan.audit_dates[0]} to {plan.audit_dates[-1]} "
        f"({len(plan.audit_dates)} complete states)"
    )
    print(f"Rolling folds: {len(plan.folds)}")
    print()
    print("Target-validity result")
    print(f"  Overall audit: {'pass' if result['target_validity_pass'] else 'fail'}")
    failed = result["validity_flags"].loc[~result["validity_flags"]["passed"]]
    if not failed.empty:
        print("  Failed checks")
        for row in failed.itertuples(index=False):
            print(
                f"  - {row.check_id}: observed={row.observed:.4f}; "
                f"threshold={row.threshold:.4f}"
            )
    print()
    print("Rolling benchmark summary")
    columns = [
        "benchmark_id",
        "mean_exact_regime_accuracy",
        "mean_balanced_accuracy",
        "mean_macro_f1",
        "mean_family_accuracy",
        "mean_family_macro_f1",
        "mean_transition_recall",
        "mean_false_transition_rate",
        "mean_baseline_margin",
        "baseline_win_rate",
    ]
    print(result["benchmark_summary"][columns].to_string(index=False))
    print()
    print("Realised target occupancy")
    print(
        result["occupancy"].loc[
            result["occupancy"]["target_level"] == "eight_state"
        ][["label", "count", "share", "median_run_months", "maximum_run_months"]]
        .to_string(index=False)
    )
    print()
    print("Validity checks")
    print(result["validity_flags"].to_string(index=False))
    if result["warnings"]:
        print()
        print("Warnings")
        for warning in result["warnings"]:
            print(f"- {warning}")
    print()
    print(f"Report: {result['report_path']}")
    print("Output files")
    for name, path in result["output_paths"].items():
        print(f"  {name}: {path}")
    print(
        "Status: target-validity diagnostic research evidence only; not "
        "candidate or production approved."
    )


if __name__ == "__main__":
    main()

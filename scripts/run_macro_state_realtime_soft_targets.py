from __future__ import annotations

import argparse

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.realtime_soft_targets_service import (
    run_macro_state_realtime_soft_target_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D real-time target reconstruction and soft-label audit."
        )
    )
    parser.add_argument(
        "--stability-id",
        default=None,
        help="Optional source v0.3.1 stability-run ID.",
    )
    args = parser.parse_args()
    result = run_macro_state_realtime_soft_target_audit(
        repository=MacroRepository(), stability_id=args.stability_id
    )
    source = result["source"]
    plan = result["plan"]
    print("Model 1D real-time target and soft-label audit complete")
    print(f"Audit ID: {result['audit_id']}")
    print(
        f"Model: {result['model_id']} v{result['model_version']} (development)"
    )
    print(f"Source stability ID: {source.stability_id}")
    print(f"Source candidate: {source.candidate_id}")
    print(
        "Source candidate v0.3.1 gate: "
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
    print("\nTarget-mode completeness")
    print(result["mode_completeness"].to_string(index=False))
    print("\nCross-vintage agreement")
    print(result["vintage_agreement"].to_string(index=False))
    print("\nSoft-target benchmark summary")
    print(result["benchmark_summary"].to_string(index=False))
    print("\nBootstrap source margin versus persistence")
    for key, value in result["bootstrap"].items():
        print(f"  {key}: {value:.6f}")
    print("\nGovernance result")
    print(
        "  Overall: "
        f"{'pass' if result['soft_target_governance_pass'] else 'fail'}"
    )
    failed = result["governance_flags"].loc[
        ~result["governance_flags"]["passed"]
    ]
    if not failed.empty:
        print("  Failed checks")
        for row in failed.itertuples(index=False):
            print(
                f"  - {row.check_id}: observed={row.observed:.4f}; "
                f"threshold={row.threshold:.4f}"
            )
    for warning in result["warnings"]:
        print(f"Warning: {warning}")
    print(f"\nReport: {result['report_path']}")
    print("Output files")
    for name, path in result["output_paths"].items():
        print(f"  {name}: {path}")
    print(
        "Status: real-time soft-target research evidence only; not candidate "
        "or production approved."
    )


if __name__ == "__main__":
    main()

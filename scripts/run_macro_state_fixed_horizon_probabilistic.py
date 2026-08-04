from __future__ import annotations

import argparse

from macropulse.macro_state.fixed_horizon_probabilistic_service import (
    run_macro_state_fixed_horizon_probabilistic_audit,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run Model 1D fixed-horizon target lock and probabilistic benchmark audit."
        )
    )
    parser.add_argument(
        "--stability-id",
        default=None,
        help="Optional source v0.3.1 stability run ID.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = run_macro_state_fixed_horizon_probabilistic_audit(
        stability_id=args.stability_id
    )
    source = result["source"]
    plan = result["plan"]
    print("Model 1D fixed-horizon target and probabilistic benchmark audit complete")
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
    print("\nTarget lock")
    print(result["target_lock"].to_string(index=False))
    print("\nMissing fixed-horizon evidence")
    if result["missing_evidence"].empty:
        print("None")
    else:
        print(result["missing_evidence"].to_string(index=False))
    print("\nProbabilistic benchmark summary")
    print(result["benchmark_summary"].to_string(index=False))
    print("\nBootstrap source margin versus soft persistence")
    for key, value in result["bootstrap"].items():
        print(f"  {key}: {value:.6f}")
    print("\nGovernance result")
    print(
        "  Overall: "
        f"{'pass' if result['fixed_horizon_governance_pass'] else 'fail'}"
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
        "Status: fixed-horizon probabilistic research evidence only; "
        "not candidate or production approved."
    )


if __name__ == "__main__":
    main()

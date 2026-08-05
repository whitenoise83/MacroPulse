from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.operations.model1d_shadow_operations import (
    run_monthly_shadow_operations,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the governed Model 1D v0.3.8 monthly prospective-shadow "
            "workflow: create one monthly prediction if absent, resolve any "
            "eligible outcomes, and write an operational monitoring report."
        )
    )
    parser.add_argument(
        "--as-of",
        help="Operational cutoff in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Do not attempt to create the current-month prediction.",
    )
    parser.add_argument(
        "--skip-resolution",
        action="store_true",
        help="Do not attempt to resolve eligible historical outcomes.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write CSV, JSON, and Markdown monitoring outputs.",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    result = run_monthly_shadow_operations(
        repository=MacroRepository(),
        as_of=as_of,
        create_prediction=not args.skip_prediction,
        resolve_outcomes=not args.skip_resolution,
        write_report=not args.no_report,
    )

    print("Model 1D prospective-shadow monthly operations complete")
    print(f"Model version: {result['model_version']}")
    print(f"Operational cutoff: {result['operation_as_of']}")
    print(f"State month: {result['state_date']}")
    print(f"Prediction action: {result['prediction_action']}")
    if result["shadow_run_id"]:
        print(f"Shadow run ID: {result['shadow_run_id']}")
    print(f"Resolved runs: {result['resolved_runs']}")
    print(f"Unresolved runs: {result['unresolved_runs']}")
    print(f"Outcome rows appended: {result['outcome_rows_appended']}")
    print(
        "Complete target months: "
        f"{result['complete_target_months']}/"
        f"{result['minimum_complete_target_months']}"
    )
    print(
        "Integrity: " + ("PASS" if result["integrity_pass"] else "FAIL")
    )
    print(
        "Comparison permitted: "
        + ("yes" if result["comparison_permitted"] else "no")
    )
    print(f"Promotion authority: {result['promotion_authority']}")
    report = result["output_paths"].get("report")
    if report:
        print(f"Monitoring report: {report}")


if __name__ == "__main__":
    main()

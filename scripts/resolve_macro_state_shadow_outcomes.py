from __future__ import annotations

import argparse
from datetime import date

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.shadow_outcomes_service import (
    resolve_macro_state_shadow_outcomes,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve eligible Model 1D v0.3.8 fixed-horizon prospective "
            "shadow outcomes without latest-revised substitution."
        )
    )
    parser.add_argument(
        "--as-of",
        help=(
            "Resolution cutoff in YYYY-MM-DD format. Defaults to today. "
            "Future cutoffs are prohibited."
        ),
    )
    parser.add_argument(
        "--shadow-run-id",
        help="Resolve one specific unresolved shadow run.",
    )
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None

    result = resolve_macro_state_shadow_outcomes(
        repository=MacroRepository(),
        as_of=as_of,
        shadow_run_id=args.shadow_run_id,
    )

    print("Model 1D prospective shadow outcome resolution complete")
    print(f"Model version: {result['model_version']}")
    print(f"Resolution cutoff: {result['resolution_as_of']}")
    print(f"Eligible shadow runs: {result['eligible_runs']}")
    print(f"Resolved shadow runs: {result['resolved_runs']}")
    print(f"Unresolved shadow runs: {result['unresolved_runs']}")
    print(f"Outcome rows appended: {result['outcome_rows_appended']}")
    print("Promotion authority: none")

    if not result["resolved"].empty:
        print()
        print("Resolved targets")
        print(
            result["resolved"][
                [
                    "shadow_run_id",
                    "state_date",
                    "strict_target_available_date",
                    "actual_family",
                    "actual_confidence",
                    "target_vintage_id",
                ]
            ].to_string(index=False)
        )
    if not result["unresolved"].empty:
        print()
        print("Unresolved targets")
        print(
            result["unresolved"][
                [
                    "shadow_run_id",
                    "state_date",
                    "persisted_expected_available_date",
                    "strict_target_available_date",
                    "unresolved_components_json",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()

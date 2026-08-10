from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.ledger import (
    PRODUCTION_COMPONENTS,
    build_forecast_evaluation_ledger,
    serialise_forecast_evaluation,
    summarise_forecast_evaluation,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MacroPulse Phase III production forecast evaluation ledger."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Evaluation information date in YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--component",
        choices=PRODUCTION_COMPONENTS,
        help="Optionally display only one production component.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the deterministic evaluation payload as JSON.",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=20,
        help="Number of most recent ledger rows to print in text mode.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()
    ledger = build_forecast_evaluation_ledger(
        repository,
        as_of=args.as_of,
        project_root=root,
    )

    if args.component:
        ledger = ledger.loc[ledger["component"] == args.component].reset_index(
            drop=True
        )

    if args.json:
        payload = serialise_forecast_evaluation(
            ledger,
            as_of=args.as_of,
        )
        print(
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return 0

    summary = summarise_forecast_evaluation(
        ledger,
        as_of=args.as_of,
    )
    print("MacroPulse Phase III production forecast evaluation ledger")
    print(f"As of: {args.as_of}")
    print("Outcome vintage: first_release")
    print("Signed error: forecast minus outcome (positive = overprediction)")
    print(f"Forecast rows: {summary['forecast_rows']}")
    print(f"Resolved: {summary['resolved_rows']}")
    print(f"Unresolved: {summary['unresolved_rows']}")
    print(
        "Structurally unavailable: "
        f"{summary['structurally_unavailable_rows']}"
    )
    print(f"Invalid/no-look-ahead failures: {summary['invalid_rows']}")
    print()

    for component, values in summary["components"].items():
        print(
            f"{component}: rows={values['forecast_rows']}; "
            f"resolved={values['resolved_rows']}; "
            f"unresolved={values['unresolved_rows']}; "
            f"structural={values['structurally_unavailable_rows']}; "
            f"invalid={values['invalid_rows']}"
        )

    if ledger.empty or args.show <= 0:
        return 0

    print()
    print(f"Most recent {min(args.show, len(ledger))} rows:")
    columns = [
        "component",
        "information_cutoff",
        "target_series",
        "target_period",
        "forecast_value",
        "outcome_value",
        "evaluation_status",
        "signed_error",
    ]
    recent = ledger.sort_values(
        ["information_cutoff", "component", "target_series"],
        ascending=[False, True, True],
        kind="stable",
    ).head(args.show)
    print(recent[columns].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

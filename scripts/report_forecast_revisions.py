from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.revisions import (
    build_revision_release_analytics,
    serialise_revision_release_analytics,
    summarise_revision_release_analytics,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MacroPulse Phase III forecast revision and scheduled "
            "release-association report."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Information date in YYYY-MM-DD form.",
    )
    parser.add_argument(
        "--component",
        choices=("1A", "1B", "1C"),
        help="Optionally restrict report to one production component.",
    )
    parser.add_argument(
        "--target-series",
        help="Optionally restrict report to one target series.",
    )
    parser.add_argument(
        "--events",
        action="store_true",
        help="Also print associated scheduled release events.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON instead of text.",
    )
    return parser


def _filter(result, *, component, target_series):
    revisions = result["revisions"]
    events = result["release_events"]

    if component:
        revisions = revisions.loc[revisions["component"] == component]
        events = events.loc[events["component"] == component]
    if target_series:
        revisions = revisions.loc[
            revisions["target_series"] == target_series
        ]
        events = events.loc[events["target_series"] == target_series]

    return {
        "revisions": revisions.reset_index(drop=True),
        "release_events": events.reset_index(drop=True),
    }


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()

    result = build_revision_release_analytics(
        repository,
        as_of=args.as_of,
        project_root=root,
    )
    result = _filter(
        result,
        component=args.component,
        target_series=args.target_series,
    )

    if args.json:
        print(
            json.dumps(
                serialise_revision_release_analytics(
                    result,
                    as_of=args.as_of,
                ),
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
        )
        return 0

    summary = summarise_revision_release_analytics(
        result,
        as_of=args.as_of,
    )
    print("MacroPulse Phase III revision and release-impact report")
    print(f"As of: {args.as_of}")
    print("Mode: read-only / descriptive association")
    print("Causal attribution: none")
    print("Automatic model action: none")
    print(
        f"Forecast rows={summary['forecast_rows']}; "
        f"baselines={summary['baseline_rows']}; "
        f"comparable revisions={summary['comparable_revision_rows']}; "
        f"nonzero revisions={summary['nonzero_revision_rows']}"
    )
    print(
        f"Release-event rows={summary['release_event_rows']}; "
        "revision rows with scheduled release="
        f"{summary['revision_rows_with_scheduled_release']}; "
        "with observed source advance="
        f"{summary['revision_rows_with_source_advance']}"
    )

    revisions = result["revisions"]
    comparable = revisions.loc[
        revisions["comparison_status"] == "comparable_revision"
    ]
    print()
    if comparable.empty:
        print("Comparable revisions: none.")
    else:
        print("Comparable revisions:")
        columns = [
            "component",
            "target_series",
            "target_period",
            "previous_information_cutoff",
            "current_information_cutoff",
            "previous_forecast_value",
            "current_forecast_value",
            "revision",
            "cumulative_revision",
            "associated_release_count",
            "advanced_source_release_count",
            "release_association_state",
        ]
        print(comparable[columns].to_string(index=False))

    if args.events:
        print()
        events = result["release_events"]
        if events.empty:
            print("Scheduled release events: none.")
        else:
            print("Scheduled release events:")
            columns = [
                "component",
                "target_series",
                "target_period",
                "release_date",
                "series_id",
                "release_name",
                "information_set_advanced",
            ]
            print(events[columns].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

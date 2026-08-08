from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.platform.status import (
    collect_platform_status,
    serialise_platform_status,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only MacroPulse Phase II platform health and freshness report."
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Information date in YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete deterministic status payload as JSON.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()
    result = collect_platform_status(
        repository,
        as_of=args.as_of,
        project_root=root,
    )

    if args.json:
        print(json.dumps(serialise_platform_status(result), indent=2, sort_keys=True))
        return 0

    readiness = result["readiness"].iloc[0]
    print("MacroPulse Phase II platform status")
    print(f"As of: {result['as_of']}")
    print(
        "Production sources ready: "
        + ("yes" if readiness["production_sources_ready"] else "no")
    )
    print(
        "Model 1D shadow valid: "
        + ("yes" if readiness["model1d_shadow_valid"] else "no")
    )
    print(
        "Platform ready for downstream: "
        + ("yes" if readiness["platform_ready_for_downstream"] else "no")
    )
    print(f"Next action: {readiness['next_action']}")
    print()
    print("Components:")
    for row in result["components"].itertuples(index=False):
        print(
            f"  {row.component}: v{row.model_version} {row.lifecycle_status}; "
            f"state={row.freshness_state}; cutoff={row.information_cutoff}; "
            f"targets={row.target_count}; stale_sources={row.stale_source_count}"
        )

    print()
    print(f"Due releases since governed runs: {len(result['due_releases'])}")
    print(
        "Upcoming releases in next 14 days: "
        f"{len(result['upcoming_releases'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

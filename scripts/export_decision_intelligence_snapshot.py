from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.decision import (
    build_decision_intelligence_snapshot,
    write_decision_intelligence_snapshot,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the deterministic MacroPulse Phase III "
            "decision-intelligence snapshot."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Information date in YYYY-MM-DD form.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()
    snapshot = build_decision_intelligence_snapshot(
        repository,
        as_of=args.as_of,
        project_root=root,
    )
    output = (
        args.output
        if args.output is not None
        else root
        / "reports"
        / "decision_intelligence_snapshots"
        / f"decision_intelligence_{args.as_of.strftime('%Y%m%d')}.json"
    )
    write_decision_intelligence_snapshot(snapshot, output)
    print(f"Wrote: {output}")
    print(f"Snapshot hash: {snapshot['snapshot_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

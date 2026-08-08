from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.platform.snapshot import build_macro_snapshot, write_macro_snapshot


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the deterministic Phase 2D MacroPulse decision-support "
            "snapshot from persisted governed state."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Snapshot cutoff in YYYY-MM-DD form. Defaults to today.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional JSON output path. Default: "
            "reports/macro_snapshots/macro_snapshot_YYYYMMDD.json"
        ),
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the complete canonical snapshot JSON to stdout.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()

    snapshot = build_macro_snapshot(
        repository,
        as_of=args.as_of,
        project_root=root,
    )

    output = args.output
    if output is None:
        output = (
            root
            / "reports"
            / "macro_snapshots"
            / f"macro_snapshot_{args.as_of.strftime('%Y%m%d')}.json"
        )
    elif not output.is_absolute():
        output = root / output

    write_macro_snapshot(snapshot, output)

    if args.stdout:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        readiness = snapshot["readiness"]
        print("MacroPulse Phase 2D deterministic macro snapshot")
        print(f"As of: {snapshot['as_of']}")
        print(f"Schema: {snapshot['snapshot_schema_version']}")
        print(f"Snapshot hash: {snapshot['snapshot_hash']}")
        print(f"Output: {output}")
        print(
            "Production sources ready: "
            + ("yes" if readiness.get("production_sources_ready") else "no")
        )
        print(
            "Model 1D shadow valid: "
            + ("yes" if readiness.get("model1d_shadow_valid") else "no")
        )
        print(
            "Platform ready for downstream: "
            + ("yes" if readiness.get("platform_ready_for_downstream") else "no")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

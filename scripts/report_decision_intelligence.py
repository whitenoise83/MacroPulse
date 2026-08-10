from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from macropulse.data.repository import MacroRepository
from macropulse.evaluation.decision import (
    build_decision_intelligence_snapshot,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only MacroPulse Phase III decision-intelligence report."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Information date in YYYY-MM-DD form.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full deterministic snapshot as JSON.",
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

    if args.json:
        print(
            json.dumps(
                snapshot,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
        )
        return 0

    summary = snapshot["summary"]
    print("MacroPulse Phase III decision-intelligence report")
    print(f"As of: {snapshot['as_of']}")
    print("Mode: read-only / deterministic presentation")
    print("Automatic model action: none")
    print("Generative AI in governed core: none")
    print(
        f"Current targets={summary['current_target_count']}; "
        f"evaluation rows={summary['evaluation_forecast_rows']}; "
        f"resolved={summary['resolved_evaluation_rows']}; "
        f"unresolved={summary['unresolved_evaluation_rows']}; "
        f"invalid={summary['invalid_evaluation_rows']}"
    )
    print(
        f"Comparable revisions={summary['comparable_revision_rows']}; "
        f"evidence flags={summary['evidence_flag_count']}"
    )
    print(f"Snapshot hash: {snapshot['snapshot_hash']}")
    print()

    columns = [
        "component",
        "target_series",
        "target_period",
        "forecast_value",
        "recent_revision",
        "evaluation_status",
        "n_resolved_history",
        "historical_context_status",
        "interval_coverage_80",
        "drift_status",
        "freshness_state",
    ]
    rows = snapshot.get("current_forecasts", [])
    if not rows:
        print("Current forecast evidence: none.")
    else:
        import pandas as pd

        frame = pd.DataFrame(rows)
        print("Current forecast evidence:")
        print(frame[columns].to_string(index=False))

    print()
    flags = snapshot.get("evidence_flags", [])
    if not flags:
        print("Evidence flags: none.")
    else:
        import pandas as pd

        print("Evidence flags:")
        print(
            pd.DataFrame(flags)[
                ["severity", "code", "component", "target_series", "detail"]
            ].to_string(index=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import pandas as pd

from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.evaluation.ledger import (
    _initial_vintage_rows,
    _period_for_target,
    _target_initial_release_date,
    collect_governed_forecasts,
    target_specs,
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh exact release-date source snapshots required by "
            "MacroPulse Phase III forecast evaluation."
        )
    )
    parser.add_argument(
        "--as-of",
        type=_parse_date,
        default=date.today(),
        help="Only cache outcome snapshots available by YYYY-MM-DD.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Replace already cached release-date snapshots.",
    )
    return parser


def required_release_snapshots(
    repository: MacroRepository,
    *,
    as_of: date,
    project_root: Path,
) -> list[dict]:
    forecasts = collect_governed_forecasts(
        repository,
        as_of=as_of,
        project_root=project_root,
    )
    targets = target_specs()
    required: dict[tuple[str, str, date], dict] = {}

    for row in forecasts.itertuples(index=False):
        component = str(row.component)
        series_id = str(row.target_series)
        target = targets[(component, series_id)]
        period = _period_for_target(target, str(row.target_period))

        initial_rows = _initial_vintage_rows(
            repository,
            target=target,
            target_period=period,
        )
        release_date = _target_initial_release_date(
            initial_rows,
            target_period=period,
        )
        if release_date is None or release_date > as_of:
            continue

        cutoff = pd.Timestamp(row.information_cutoff).date()
        if cutoff >= release_date:
            continue

        key = (component, series_id, release_date)
        required[key] = {
            "component": component,
            "series_id": series_id,
            "target_name": target.name,
            "target_period": str(row.target_period),
            "release_date": release_date,
            "start_date": target.start_date,
        }

    return [
        required[key]
        for key in sorted(
            required,
            key=lambda item: (item[2], item[0], item[1]),
        )
    ]


def main() -> int:
    args = build_parser().parse_args()
    if args.as_of > date.today():
        raise ValueError("Snapshot refresh as-of date cannot be in the future.")

    root = Path(__file__).resolve().parents[1]
    repository = MacroRepository()
    repository.initialise()
    client = FredClient()

    items = required_release_snapshots(
        repository,
        as_of=args.as_of,
        project_root=root,
    )

    print("MacroPulse Phase III outcome snapshot refresh")
    print(f"As of: {args.as_of}")
    print("Scope: source evidence only")
    print("Governed forecast mutations: none")
    print("Model execution: none")
    print(f"Required release snapshots: {len(items)}")

    downloaded = 0
    skipped_cached = 0

    for item in items:
        series_id = item["series_id"]
        release_date = item["release_date"]

        if (
            not args.refresh
            and repository.snapshot_is_cached(series_id, release_date)
        ):
            skipped_cached += 1
            print(
                f"SKIP cached {item['component']} {series_id} "
                f"{item['target_period']} @ {release_date}"
            )
            continue

        print(
            f"DOWNLOAD {item['component']} {series_id} "
            f"{item['target_period']} @ {release_date}"
        )
        frame = client.get_observations_as_of(
            series_id=series_id,
            observation_start=item["start_date"],
            as_of_date=release_date.isoformat(),
        )
        if frame.empty:
            raise RuntimeError(
                f"FRED/ALFRED returned an empty release snapshot for "
                f"{series_id} on {release_date}."
            )
        repository.replace_historical_snapshot(
            series_id=series_id,
            as_of_date=release_date,
            frame=frame,
        )
        downloaded += 1
        print(f"  cached rows: {len(frame):,}")

    print(
        f"Finished. Downloaded={downloaded}; "
        f"already_cached={skipped_cached}; total={len(items)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

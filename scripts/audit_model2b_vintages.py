from __future__ import annotations

import argparse

import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, audit_snapshot
from macropulse.data.repository import MacroRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only audit of cached Model 2 historical vintages.")
    parser.add_argument("--as-of", action="append", default=[], help="Exact cached date YYYY-MM-DD; may repeat.")
    parser.add_argument("--all-common", action="store_true", help="Audit every date cached successfully for all four series.")
    parser.add_argument("--limit", type=int, default=12, help="Default: latest N common cached dates.")
    return parser.parse_args()


def common_cached_dates(repo: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = (
        "SELECT as_of_date FROM snapshot_downloads "
        "WHERE status = 'success' AND series_id IN (" + placeholders + ") "
        "GROUP BY as_of_date HAVING COUNT(DISTINCT series_id) = ? ORDER BY as_of_date"
    )
    params = [*REQUIRED_SERIES, len(REQUIRED_SERIES)]
    with repo.connect(read_only=True) as connection:
        return [row[0] for row in connection.execute(query, params).fetchall()]


def main() -> int:
    args = parse_args()
    repo = MacroRepository()
    cached = common_cached_dates(repo)

    print("Model 2B.1 historical-vintage cache audit")
    print("Required series: " + ", ".join(REQUIRED_SERIES))
    print("Common cached dates: " + str(len(cached)))
    if cached:
        print("Common cache range: " + str(cached[0]) + " -> " + str(cached[-1]))

    if args.as_of:
        requested = [pd.Timestamp(value).date() for value in args.as_of]
    elif args.all_common:
        requested = cached
    else:
        requested = cached[-max(0, args.limit):]

    if not requested:
        print("Status: COVERAGE_NOT_READY")
        print("No exact as-of dates are cached successfully for all four required series.")
        return 2

    print()
    print("as_of       raw_rows complete_q first_q last_q lag_q GDPC1 PCEPILFE UNRATE FEDFUNDS notices")
    print("-" * 100)
    for as_of_date in requested:
        snapshot = repo.historical_snapshot(as_of_date=as_of_date, series_ids=list(REQUIRED_SERIES))
        audit = audit_snapshot(snapshot, as_of_date)
        c = audit.row_counts
        print(
            f"{as_of_date} {audit.raw_rows:8d} {audit.complete_joint_quarters:10d} "
            f"{(audit.first_joint_quarter or '-'):7s} {(audit.last_joint_quarter or '-'):6s} "
            f"{str(audit.lag_quarters) if audit.lag_quarters is not None else '-':5s} "
            f"{c['GDPC1']:5d} {c['PCEPILFE']:8d} {c['UNRATE']:6d} {c['FEDFUNDS']:8d} "
            f"{','.join(audit.notices) or '-'}"
        )

    print()
    print("Audit is read-only. No snapshots were downloaded or modified.")
    print("No estimation/evaluation start date has been selected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

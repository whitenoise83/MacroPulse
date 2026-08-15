from __future__ import annotations

import argparse

from macropulse.bvar.data import REQUIRED_SERIES
from macropulse.bvar.origins import derive_origin_grid, validate_origin_grid
from macropulse.data.repository import MacroRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Model 2B.2 pseudo-real-time origin-grid audit."
    )
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print every origin state; default prints summary plus recent rows.",
    )
    return parser.parse_args()


def common_cached_dates(repo: MacroRepository):
    placeholders = ", ".join(["?"] * len(REQUIRED_SERIES))
    query = (
        "SELECT as_of_date FROM snapshot_downloads "
        "WHERE status = 'success' AND series_id IN (" + placeholders + ") "
        "GROUP BY as_of_date "
        "HAVING COUNT(DISTINCT series_id) = ? "
        "ORDER BY as_of_date"
    )
    params = [*REQUIRED_SERIES, len(REQUIRED_SERIES)]
    with repo.connect(read_only=True) as connection:
        return [
            row[0]
            for row in connection.execute(query, params).fetchall()
        ]


def main() -> int:
    args = parse_args()
    repo = MacroRepository()
    cutoffs = common_cached_dates(repo)

    if not cutoffs:
        print("Model 2B.2 origin-grid audit: COVERAGE_NOT_READY")
        print("No successful common cached cutoff exists.")
        return 2

    grid = derive_origin_grid(
        cutoffs,
        lambda cutoff: repo.historical_snapshot(
            as_of_date=cutoff,
            series_ids=list(REQUIRED_SERIES),
        ),
    )
    validate_origin_grid(grid)

    admissible = grid[grid["admissible_for_pseudo_real_time"]]

    print("Model 2B.2 pseudo-real-time origin-grid audit")
    print("Required series: " + ", ".join(REQUIRED_SERIES))
    print("Common cached cutoffs: " + str(len(cutoffs)))
    print("Cache range: " + str(cutoffs[0]) + " -> " + str(cutoffs[-1]))
    print("Observed origin states: " + str(len(grid)))
    print("Admissible non-left-censored origins: " + str(len(admissible)))
    print(
        "First observed state: "
        + str(grid.iloc[0]["origin_quarter"])
        + " at "
        + str(grid.iloc[0]["as_of_date"])
        + " [LEFT_CENSORED]"
    )
    print(
        "Last observed state: "
        + str(grid.iloc[-1]["origin_quarter"])
        + " at "
        + str(grid.iloc[-1]["as_of_date"])
    )
    print()

    display = grid if args.show_all else grid.tail(12)
    print(
        "origin_q as_of       admissible left_censored "
        "h1      h2      h4      h8"
    )
    print("-" * 82)
    for row in display.itertuples(index=False):
        print(
            f"{row.origin_quarter:8s} {row.as_of_date} "
            f"{str(bool(row.admissible_for_pseudo_real_time)):10s} "
            f"{str(bool(row.left_censored)):13s} "
            f"{row.target_h1:7s} {row.target_h2:7s} "
            f"{row.target_h4:7s} {row.target_h8:7s}"
        )

    print()
    print("Audit is read-only. No snapshot was downloaded or modified.")
    print("No estimation/evaluation start date has been selected.")
    print("No Model 2 candidate has been selected.")
    print("Historical Model 1 outputs were not fabricated or backfilled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

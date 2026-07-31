from __future__ import annotations

import argparse
import json

import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.vintage import structural_missing_reason


IGNORED_NOTICE_KINDS = {"pending", "training_warmup", "structural_missing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reclassify known structurally unavailable labour outcomes in an existing "
            "vintage backtest without rerunning ALFRED downloads or model estimation."
        )
    )
    parser.add_argument("--backtest-id", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = MacroRepository()
    repository.initialise()
    run = repository.query_df(
        "SELECT * FROM labour_vintage_backtest_runs WHERE backtest_id = ?",
        [args.backtest_id],
    )
    if run.empty:
        raise RuntimeError(f"Labour vintage backtest {args.backtest_id} was not found.")

    row = run.iloc[0]
    notices = json.loads(row.get("notices_json") or "[]")
    repaired = 0
    for notice in notices:
        reason = structural_missing_reason(
            str(notice.get("target_series", "")),
            pd.Period(str(notice.get("target_period")), freq="M"),
        )
        if reason is not None and notice.get("kind") == "missing_release":
            notice["kind"] = "structural_missing"
            notice["message"] = reason
            repaired += 1

    hard_issues = [
        notice for notice in notices if notice.get("kind") not in IGNORED_NOTICE_KINDS
    ]
    status = "success" if not hard_issues else "partial"
    notes = str(row.get("notes") or "")
    audit_note = (
        " Structural-unavailability classification repaired without changing forecasts "
        "or realised outcomes."
    )
    if audit_note.strip() not in notes:
        notes = (notes + audit_note).strip()

    with repository.connect() as connection:
        connection.execute(
            """
            UPDATE labour_vintage_backtest_runs
            SET status = ?, notices_json = ?, notes = ?
            WHERE backtest_id = ?
            """,
            [status, json.dumps(notices, default=str), notes, args.backtest_id],
        )

    print("Model 1C structural-missing repair complete")
    print(f"Backtest ID: {args.backtest_id}")
    print(f"Reclassified notices: {repaired}")
    print(f"Remaining hard issues: {len(hard_issues)}")
    print(f"Backtest status: {status}")
    if hard_issues:
        print("First remaining hard issues")
        print(json.dumps(hard_issues[:10], indent=2, default=str))


if __name__ == "__main__":
    main()

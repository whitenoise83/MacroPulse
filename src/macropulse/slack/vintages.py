from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Callable, Iterable

import pandas as pd

from macropulse.slack.data import REQUIRED_SERIES, build_quarterly_panel, normalise_snapshot


INFORMATION_SET_COLUMNS = (
    "information_set_id",
    "as_of_date",
    "panel_first_quarter",
    "panel_last_quarter",
    "complete_joint_quarters",
    "source_snapshot_hash",
    "left_censored",
    "admissible_for_pseudo_real_time",
)


def canonical_snapshot_hash(snapshot: pd.DataFrame, as_of_date: date) -> str:
    frame = normalise_snapshot(snapshot, as_of_date)
    frame = frame.sort_values(["series_id", "observation_date", "value"])
    parts = [f"as_of={as_of_date.isoformat()}"]
    for row in frame.itertuples(index=False):
        parts.append(
            f"{row.series_id}|{row.observation_date.date().isoformat()}|"
            f"{float(row.value):.17g}"
        )
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def information_set_id(as_of_date: date, snapshot_hash: str) -> str:
    payload = f"model3b|{as_of_date.isoformat()}|{snapshot_hash}"
    return sha256(payload.encode("utf-8")).hexdigest()


def derive_information_set_inventory(
    cutoffs: Iterable[date],
    snapshot_loader: Callable[[date], pd.DataFrame],
) -> pd.DataFrame:
    records: list[dict] = []
    previous_last: pd.Period | None = None

    for as_of_date in sorted(set(cutoffs)):
        snapshot = snapshot_loader(as_of_date)
        panel = build_quarterly_panel(snapshot, as_of_date)
        if panel.empty:
            raise ValueError(
                "Information set has no complete joint quarter: "
                + as_of_date.isoformat()
            )

        current_last = panel.index[-1]
        if previous_last is not None:
            delta = current_last.ordinal - previous_last.ordinal
            if delta < 0:
                raise ValueError("panel_last_quarter decreased across cutoffs.")
            if delta > 1:
                raise ValueError("panel_last_quarter skipped one or more quarters.")
            if delta == 0:
                continue

        snap_hash = canonical_snapshot_hash(snapshot, as_of_date)
        left_censored = previous_last is None
        records.append(
            {
                "information_set_id": information_set_id(as_of_date, snap_hash),
                "as_of_date": as_of_date,
                "panel_first_quarter": str(panel.index[0]),
                "panel_last_quarter": str(current_last),
                "complete_joint_quarters": int(len(panel)),
                "source_snapshot_hash": snap_hash,
                "left_censored": left_censored,
                "admissible_for_pseudo_real_time": not left_censored,
            }
        )
        previous_last = current_last

    return pd.DataFrame.from_records(records, columns=list(INFORMATION_SET_COLUMNS))


def validate_information_set_inventory(inventory: pd.DataFrame) -> None:
    if inventory.empty:
        raise ValueError("Information-set inventory is empty.")
    missing = sorted(set(INFORMATION_SET_COLUMNS) - set(inventory.columns))
    if missing:
        raise ValueError("Information-set inventory missing: " + ", ".join(missing))

    last = pd.PeriodIndex(inventory["panel_last_quarter"], freq="Q")
    if last.has_duplicates:
        raise ValueError("Information-set inventory has duplicate terminal quarters.")
    if len(last) > 1:
        diffs = [last[i].ordinal - last[i - 1].ordinal for i in range(1, len(last))]
        if any(value != 1 for value in diffs):
            raise ValueError("Terminal-quarter sequence must advance exactly one quarter.")

    left = inventory["left_censored"].astype(bool)
    if int(left.sum()) != 1 or not bool(left.iloc[0]):
        raise ValueError("Exactly the first information set must be left-censored.")

    admissible = inventory["admissible_for_pseudo_real_time"].astype(bool)
    if bool(admissible.iloc[0]):
        raise ValueError("Left-censored first information set may not be admissible.")
    if len(inventory) > 1 and not bool(admissible.iloc[1:].all()):
        raise ValueError("All later information sets must be admissible inventory.")

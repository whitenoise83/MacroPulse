from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Callable, Iterable

import pandas as pd

from macropulse.bvar.data import REQUIRED_SERIES, audit_snapshot


ORIGIN_COLUMNS = (
    "origin_id",
    "origin_quarter",
    "as_of_date",
    "panel_first_quarter",
    "panel_last_quarter",
    "complete_joint_quarters",
    "lag_quarters",
    "source_snapshot_hash",
    "left_censored",
    "admissible_for_pseudo_real_time",
    "target_h1",
    "target_h2",
    "target_h4",
    "target_h8",
)


def _empty_origin_grid() -> pd.DataFrame:
    return pd.DataFrame(columns=list(ORIGIN_COLUMNS))


def _canonical_snapshot_hash(snapshot: pd.DataFrame, as_of_date: date) -> str:
    required = {"series_id", "observation_date", "value"}
    missing = sorted(required - set(snapshot.columns))
    if missing:
        raise ValueError(
            "Snapshot missing required columns for hashing: " + ", ".join(missing)
        )

    frame = snapshot.loc[:, ["series_id", "observation_date", "value"]].copy()
    frame["series_id"] = frame["series_id"].astype(str)
    frame["observation_date"] = pd.to_datetime(
        frame["observation_date"], errors="coerce"
    )
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["series_id", "observation_date", "value"])
    frame = frame[frame["series_id"].isin(REQUIRED_SERIES)].copy()
    frame = frame.sort_values(["series_id", "observation_date", "value"])

    parts = [f"as_of={as_of_date.isoformat()}"]
    for row in frame.itertuples(index=False):
        parts.append(
            f"{row.series_id}|{row.observation_date.date().isoformat()}|"
            f"{float(row.value):.17g}"
        )
    return sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _origin_id(
    origin_quarter: pd.Period,
    as_of_date: date,
    source_snapshot_hash: str,
) -> str:
    payload = (
        "model2b2|"
        + str(origin_quarter)
        + "|"
        + as_of_date.isoformat()
        + "|"
        + source_snapshot_hash
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def derive_origin_grid(
    cutoffs: Iterable[date],
    snapshot_loader: Callable[[date], pd.DataFrame],
) -> pd.DataFrame:
    ordered = sorted(set(cutoffs))
    if not ordered:
        return _empty_origin_grid()

    records: list[dict] = []
    previous_last: pd.Period | None = None

    for as_of_date in ordered:
        snapshot = snapshot_loader(as_of_date)
        audit = audit_snapshot(snapshot, as_of_date)

        if audit.last_joint_quarter is None:
            raise ValueError(
                "Common cached cutoff has no complete joint quarter: "
                + as_of_date.isoformat()
            )

        current_last = pd.Period(audit.last_joint_quarter, freq="Q")

        if previous_last is not None:
            delta = current_last.ordinal - previous_last.ordinal
            if delta < 0:
                raise ValueError(
                    "last_complete_quarter decreased at "
                    + as_of_date.isoformat()
                    + f": {previous_last} -> {current_last}"
                )
            if delta > 1:
                raise ValueError(
                    "last_complete_quarter skipped one or more quarters at "
                    + as_of_date.isoformat()
                    + f": {previous_last} -> {current_last}"
                )
            if delta == 0:
                continue

        left_censored = previous_last is None
        snapshot_hash = _canonical_snapshot_hash(snapshot, as_of_date)
        records.append(
            {
                "origin_id": _origin_id(current_last, as_of_date, snapshot_hash),
                "origin_quarter": str(current_last),
                "as_of_date": as_of_date,
                "panel_first_quarter": audit.first_joint_quarter,
                "panel_last_quarter": audit.last_joint_quarter,
                "complete_joint_quarters": audit.complete_joint_quarters,
                "lag_quarters": audit.lag_quarters,
                "source_snapshot_hash": snapshot_hash,
                "left_censored": left_censored,
                "admissible_for_pseudo_real_time": not left_censored,
                "target_h1": str(current_last + 1),
                "target_h2": str(current_last + 2),
                "target_h4": str(current_last + 4),
                "target_h8": str(current_last + 8),
            }
        )
        previous_last = current_last

    frame = pd.DataFrame.from_records(records)
    if frame.empty:
        return _empty_origin_grid()
    return frame.loc[:, list(ORIGIN_COLUMNS)]


def validate_origin_grid(grid: pd.DataFrame) -> None:
    if grid.empty:
        raise ValueError("Origin grid is empty.")

    missing = sorted(set(ORIGIN_COLUMNS) - set(grid.columns))
    if missing:
        raise ValueError(
            "Origin grid missing required columns: " + ", ".join(missing)
        )

    quarters = pd.PeriodIndex(grid["origin_quarter"], freq="Q")
    if quarters.has_duplicates:
        raise ValueError("Origin grid contains duplicate origin quarters.")

    if len(quarters) > 1:
        diffs = [
            quarters[i].ordinal - quarters[i - 1].ordinal
            for i in range(1, len(quarters))
        ]
        if any(value != 1 for value in diffs):
            raise ValueError(
                "Origin grid quarter sequence must advance exactly one quarter."
            )

    left = grid["left_censored"].astype(bool)
    if int(left.sum()) != 1 or not bool(left.iloc[0]):
        raise ValueError(
            "Origin grid must contain exactly one first-row left-censored state."
        )

    admissible = grid["admissible_for_pseudo_real_time"].astype(bool)
    if bool(admissible.iloc[0]):
        raise ValueError("Left-censored first state may not be admissible.")
    if len(grid) > 1 and not bool(admissible.iloc[1:].all()):
        raise ValueError(
            "All non-left-censored origin states must be admissible inventory."
        )

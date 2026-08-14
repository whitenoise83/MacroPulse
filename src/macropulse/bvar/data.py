from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log

import pandas as pd


REQUIRED_SERIES = ("GDPC1", "PCEPILFE", "UNRATE", "FEDFUNDS")

OUTPUT_COLUMNS = (
    "real_gdp_growth",
    "core_pce_inflation",
    "unemployment_rate",
    "policy_rate",
)


@dataclass(frozen=True)
class VintagePanelAudit:
    as_of_date: date
    raw_rows: int
    row_counts: dict[str, int]
    complete_joint_quarters: int
    first_joint_quarter: str | None
    last_joint_quarter: str | None
    lag_quarters: int | None
    notices: tuple[str, ...]


def _empty_panel() -> pd.DataFrame:
    frame = pd.DataFrame(columns=list(OUTPUT_COLUMNS))
    frame.index = pd.PeriodIndex([], freq="Q", name="quarter")
    return frame


def _normalise_snapshot(snapshot: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    required = {"series_id", "observation_date", "value"}
    missing = sorted(required - set(snapshot.columns))
    if missing:
        raise ValueError("Snapshot missing required columns: " + ", ".join(missing))

    frame = snapshot.loc[:, ["series_id", "observation_date", "value"]].copy()
    frame["series_id"] = frame["series_id"].astype(str)
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["series_id", "observation_date", "value"])

    future = frame["observation_date"].dt.date > as_of_date
    if bool(future.any()):
        examples = (
            frame.loc[future, ["series_id", "observation_date"]]
            .head(5)
            .astype(str)
            .to_dict("records")
        )
        raise ValueError(
            "Snapshot contains observation_date later than as_of_date: "
            + repr(examples)
        )

    frame = frame[frame["series_id"].isin(REQUIRED_SERIES)].copy()

    duplicate = frame.duplicated(
        subset=["series_id", "observation_date"],
        keep=False,
    )
    if bool(duplicate.any()):
        examples = (
            frame.loc[
                duplicate,
                ["series_id", "observation_date", "value"],
            ]
            .sort_values(["series_id", "observation_date"])
            .head(10)
            .astype(str)
            .to_dict("records")
        )
        raise ValueError(
            "Snapshot contains duplicate exact-vintage rows for "
            "(series_id, observation_date): "
            + repr(examples)
        )

    frame["quarter"] = frame["observation_date"].dt.to_period("Q")
    frame["month"] = frame["observation_date"].dt.month
    frame = frame.sort_values(["series_id", "observation_date"])
    return frame


def _native_quarter(frame: pd.DataFrame, series_id: str) -> pd.Series:
    part = frame[frame["series_id"] == series_id]
    if part.empty:
        return pd.Series(dtype=float)
    result = part.groupby("quarter", sort=True)["value"].last()
    result.index = pd.PeriodIndex(result.index, freq="Q")
    return result.astype(float)


def _quarter_end_month(frame: pd.DataFrame, series_id: str) -> pd.Series:
    part = frame[frame["series_id"] == series_id].copy()
    if part.empty:
        return pd.Series(dtype=float)

    quarter_end_months = part["quarter"].dt.end_time.dt.month
    part = part[part["month"].eq(quarter_end_months)]
    if part.empty:
        return pd.Series(dtype=float)

    result = part.groupby("quarter", sort=True)["value"].last()
    result.index = pd.PeriodIndex(result.index, freq="Q")
    return result.astype(float)


def _three_month_mean(frame: pd.DataFrame, series_id: str) -> pd.Series:
    part = frame[frame["series_id"] == series_id].copy()
    if part.empty:
        return pd.Series(dtype=float)

    grouped = part.groupby("quarter", sort=True)
    counts = grouped["month"].nunique()
    means = grouped["value"].mean()
    result = means[counts.eq(3)]
    result.index = pd.PeriodIndex(result.index, freq="Q")
    return result.astype(float)


def _annualised_qoq_log(levels: pd.Series) -> pd.Series:
    levels = levels.sort_index().astype(float)
    if bool((levels <= 0).any()):
        raise ValueError("Log-growth transformation requires strictly positive levels.")
    return 400.0 * levels.map(log).diff()


def build_complete_quarter_panel(
    snapshot: pd.DataFrame,
    as_of_date: date,
) -> pd.DataFrame:
    """Build the no-look-ahead complete-quarter BVAR panel for one exact vintage."""
    frame = _normalise_snapshot(snapshot, as_of_date)
    if frame.empty:
        return _empty_panel()

    gdp_level = _native_quarter(frame, "GDPC1")
    pce_level = _quarter_end_month(frame, "PCEPILFE")

    # UNRATE is a stock variable in Model 2: use the observed quarter-end month.
    # Do not construct a quarterly average that would require a fabricated
    # October 2025 CPS observation.
    unemployment = _quarter_end_month(frame, "UNRATE")

    # FEDFUNDS remains a quarterly exposure measure and requires all three months.
    policy = _three_month_mean(frame, "FEDFUNDS")

    panel = pd.concat(
        {
            "real_gdp_growth": _annualised_qoq_log(gdp_level),
            "core_pce_inflation": _annualised_qoq_log(pce_level),
            "unemployment_rate": unemployment,
            "policy_rate": policy,
        },
        axis=1,
    )
    panel = panel.dropna(how="any").sort_index()
    panel.index = pd.PeriodIndex(panel.index, freq="Q", name="quarter")
    return panel.loc[:, list(OUTPUT_COLUMNS)]


def audit_snapshot(
    snapshot: pd.DataFrame,
    as_of_date: date,
) -> VintagePanelAudit:
    frame = _normalise_snapshot(snapshot, as_of_date)
    row_counts = {
        series_id: int((frame["series_id"] == series_id).sum())
        for series_id in REQUIRED_SERIES
    }
    notices: list[str] = []
    for series_id, count in row_counts.items():
        if count == 0:
            notices.append("missing_series:" + series_id)

    panel = build_complete_quarter_panel(snapshot, as_of_date)
    if panel.empty:
        return VintagePanelAudit(
            as_of_date=as_of_date,
            raw_rows=len(frame),
            row_counts=row_counts,
            complete_joint_quarters=0,
            first_joint_quarter=None,
            last_joint_quarter=None,
            lag_quarters=None,
            notices=tuple(notices + ["no_complete_joint_quarter"]),
        )

    last_quarter = panel.index[-1]
    cutoff_quarter = pd.Period(as_of_date, freq="Q")
    lag_quarters = int(cutoff_quarter.ordinal - last_quarter.ordinal)

    return VintagePanelAudit(
        as_of_date=as_of_date,
        raw_rows=len(frame),
        row_counts=row_counts,
        complete_joint_quarters=len(panel),
        first_joint_quarter=str(panel.index[0]),
        last_joint_quarter=str(last_quarter),
        lag_quarters=lag_quarters,
        notices=tuple(notices),
    )

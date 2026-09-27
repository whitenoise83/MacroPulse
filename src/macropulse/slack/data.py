from __future__ import annotations

from datetime import date
from math import log

import pandas as pd


REQUIRED_SERIES = ("GDPC1", "UNRATE", "PCEPILFE")
OUTPUT_COLUMNS = (
    "real_gdp_level",
    "real_gdp_log",
    "unemployment_rate",
    "core_pce_level",
    "core_pce_inflation",
)


def _empty_panel() -> pd.DataFrame:
    frame = pd.DataFrame(columns=list(OUTPUT_COLUMNS))
    frame.index = pd.PeriodIndex([], freq="Q", name="quarter")
    return frame


def normalise_snapshot(snapshot: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    required = {"series_id", "observation_date", "value"}
    missing = sorted(required - set(snapshot.columns))
    if missing:
        raise ValueError("Snapshot missing required columns: " + ", ".join(missing))

    frame = snapshot.loc[:, ["series_id", "observation_date", "value"]].copy()
    frame["series_id"] = frame["series_id"].astype(str)
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    frame = frame.dropna(subset=["series_id", "observation_date", "value"])
    frame = frame[frame["series_id"].isin(REQUIRED_SERIES)].copy()

    future = frame["observation_date"].dt.date > as_of_date
    if bool(future.any()):
        raise ValueError("Snapshot contains observation_date later than as_of_date.")

    duplicate = frame.duplicated(["series_id", "observation_date"], keep=False)
    if bool(duplicate.any()):
        raise ValueError(
            "Snapshot contains duplicate exact-vintage rows for "
            "(series_id, observation_date)."
        )

    frame["quarter"] = frame["observation_date"].dt.to_period("Q")
    frame["month"] = frame["observation_date"].dt.month
    return frame.sort_values(["series_id", "observation_date"])


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
    end_month = part["quarter"].dt.end_time.dt.month
    part = part[part["month"].eq(end_month)]
    if part.empty:
        return pd.Series(dtype=float)
    result = part.groupby("quarter", sort=True)["value"].last()
    result.index = pd.PeriodIndex(result.index, freq="Q")
    return result.astype(float)


def build_quarterly_panel(snapshot: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
    """Transform one governed exact-vintage snapshot into Model 3 quarterly data."""
    frame = normalise_snapshot(snapshot, as_of_date)
    if frame.empty:
        return _empty_panel()

    gdp = _native_quarter(frame, "GDPC1").sort_index()
    if bool((gdp <= 0).any()):
        raise ValueError("Real GDP level must be strictly positive.")

    pce = _quarter_end_month(frame, "PCEPILFE").sort_index()
    if bool((pce <= 0).any()):
        raise ValueError("Core PCE level must be strictly positive.")

    unemployment = _quarter_end_month(frame, "UNRATE").sort_index()

    panel = pd.concat(
        {
            "real_gdp_level": gdp,
            "real_gdp_log": gdp.map(log),
            "unemployment_rate": unemployment,
            "core_pce_level": pce,
            "core_pce_inflation": 400.0 * pce.map(log).diff(),
        },
        axis=1,
    )
    panel = panel.dropna(how="any").sort_index()
    panel.index = pd.PeriodIndex(panel.index, freq="Q", name="quarter")
    return panel.loc[:, list(OUTPUT_COLUMNS)]

from __future__ import annotations

import time
from datetime import date

import pandas as pd

from macropulse.config import SeriesDefinition
from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.processing.transforms import transform_series


def is_recent_unreleased_period(target_period: pd.Period) -> bool:
    current_period = pd.Timestamp(date.today()).to_period("Q")
    return target_period >= current_period - 1


def target_actual_from_snapshot(
    snapshot: pd.DataFrame,
    target_definition: SeriesDefinition,
    target_period: pd.Period,
) -> float:
    target_rows = snapshot.loc[snapshot["series_id"] == target_definition.series_id]
    if target_rows.empty:
        raise ValueError(f"No target snapshot was found for {target_definition.series_id}.")
    values = (
        target_rows.assign(observation_date=pd.to_datetime(target_rows["observation_date"]))
        .sort_values("observation_date")
        .set_index("observation_date")["value"]
    )
    transformed = transform_series(values, target_definition.transform)
    transformed.index = transformed.index.to_period("Q")
    quarterly = transformed.groupby(level=0).last()
    if target_period not in quarterly.index or pd.isna(quarterly.loc[target_period]):
        raise ValueError(f"No realised target is available for {target_period}.")
    return float(quarterly.loc[target_period])


def ensure_snapshot(
    repository: MacroRepository,
    client: FredClient,
    definition: SeriesDefinition,
    as_of_date: pd.Timestamp,
    refresh: bool,
    pause_seconds: float,
) -> None:
    as_of = as_of_date.date()
    if not refresh and repository.snapshot_is_cached(definition.series_id, as_of):
        return
    frame = client.get_observations_as_of(
        series_id=definition.series_id,
        observation_start=definition.start_date,
        as_of_date=as_of.isoformat(),
    )
    repository.replace_historical_snapshot(
        series_id=definition.series_id,
        as_of_date=as_of,
        frame=frame,
    )
    if pause_seconds > 0:
        time.sleep(pause_seconds)

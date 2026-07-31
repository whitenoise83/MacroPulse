from __future__ import annotations

import time
from datetime import date

import pandas as pd

from macropulse.data.fred_client import FredClient
from macropulse.data.repository import MacroRepository
from macropulse.labour.config import LabourSeriesDefinition
from macropulse.labour.dataset import build_monthly_levels
from macropulse.processing.transforms import transform_series

STRUCTURALLY_UNAVAILABLE_TARGETS: dict[tuple[str, str], str] = {
    ("UNRATE", "2025-10"): (
        "The October 2025 household survey was not collected during the federal "
        "appropriations lapse, so no October 2025 unemployment-rate estimate exists."
    ),
}


def structural_missing_reason(
    series_id: str,
    target_period: pd.Period,
) -> str | None:
    return STRUCTURALLY_UNAVAILABLE_TARGETS.get((str(series_id), str(target_period)))


def is_recent_unreleased_month(target_period: pd.Period) -> bool:
    current = pd.Timestamp(date.today()).to_period("M")
    return target_period >= current - 1


def ensure_labour_snapshot(
    repository: MacroRepository,
    client: FredClient,
    definition: LabourSeriesDefinition,
    as_of_date: date,
    refresh: bool = False,
    pause_seconds: float = 0.0,
) -> None:
    if not refresh and repository.snapshot_is_cached(definition.series_id, as_of_date):
        return
    frame = client.get_observations_as_of(
        series_id=definition.series_id,
        observation_start=definition.start_date,
        as_of_date=as_of_date.isoformat(),
    )
    repository.replace_historical_snapshot(
        series_id=definition.series_id,
        as_of_date=as_of_date,
        frame=frame,
    )
    if pause_seconds > 0:
        time.sleep(pause_seconds)


def target_actual_from_release_snapshot(
    snapshot: pd.DataFrame,
    target_definition: LabourSeriesDefinition,
    target_period: pd.Period,
) -> float:
    levels = build_monthly_levels(snapshot)
    if target_definition.series_id not in levels:
        raise ValueError(
            f"No target release snapshot is available for {target_definition.series_id}."
        )
    transformed = transform_series(
        levels[target_definition.series_id], target_definition.transform
    ).dropna()
    if target_period not in transformed.index:
        raise ValueError(
            f"No realised initial-release labour outcome is available for "
            f"{target_definition.series_id} {target_period}."
        )
    return float(transformed.loc[target_period])

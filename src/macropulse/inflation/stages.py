from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass(frozen=True)
class InflationForecastStage:
    code: str
    label: str
    description: str


INFLATION_FORECAST_STAGES: tuple[InflationForecastStage, ...] = (
    InflationForecastStage(
        "month_open",
        "Month open",
        "Information available on the first calendar day of the target month.",
    ),
    InflationForecastStage(
        "mid_month",
        "Mid-month",
        "Information available on the 15th calendar day of the target month.",
    ),
    InflationForecastStage(
        "month_end",
        "Month end",
        "Information available at the end of the target month.",
    ),
    InflationForecastStage(
        "pre_release",
        "Pre-release",
        "Information available one calendar day before the target index's initial release.",
    ),
)

INFLATION_STAGE_MAP = {stage.code: stage for stage in INFLATION_FORECAST_STAGES}


def validate_inflation_stage_codes(stage_codes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    unknown = [code for code in stage_codes if code not in INFLATION_STAGE_MAP]
    if unknown:
        raise ValueError(
            f"Unknown inflation forecast stages: {unknown}. "
            f"Valid stages are {sorted(INFLATION_STAGE_MAP)}."
        )
    return tuple(stage_codes)


def inflation_stage_forecast_date(
    target_period: pd.Period | str,
    stage_code: str,
    release_date: date | None = None,
) -> date:
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="M")
    )
    if stage_code == "month_open":
        return period.start_time.date()
    if stage_code == "mid_month":
        return date(period.year, period.month, 15)
    if stage_code == "month_end":
        return period.end_time.normalize().date()
    if stage_code == "pre_release":
        if release_date is None:
            raise ValueError("pre_release requires an initial release date.")
        return release_date - timedelta(days=1)
    raise ValueError(f"Unknown inflation forecast stage: {stage_code}")

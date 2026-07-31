from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass(frozen=True)
class ForecastStage:
    code: str
    label: str
    description: str


FORECAST_STAGES: tuple[ForecastStage, ...] = (
    ForecastStage(
        "early_quarter",
        "Early quarter",
        "Information available on the 15th day of the quarter's first month.",
    ),
    ForecastStage(
        "after_month_1",
        "After month 1 releases",
        "Information available on the 15th day of the quarter's second month.",
    ),
    ForecastStage(
        "after_month_2",
        "After month 2 releases",
        "Information available on the 15th day of the quarter's third month.",
    ),
    ForecastStage(
        "quarter_end",
        "Quarter end",
        "Information available at the calendar quarter end.",
    ),
    ForecastStage(
        "pre_advance_release",
        "Pre-advance release",
        "Information available one calendar day before the initial GDP release.",
    ),
)

STAGE_MAP = {stage.code: stage for stage in FORECAST_STAGES}


def validate_stage_codes(stage_codes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    unknown = [code for code in stage_codes if code not in STAGE_MAP]
    if unknown:
        raise ValueError(
            f"Unknown forecast stages: {unknown}. Valid stages are {sorted(STAGE_MAP)}."
        )
    return tuple(stage_codes)


def _month_date(target_period: pd.Period, month_offset: int, day: int = 15) -> date:
    start = target_period.start_time.normalize()
    month = start + pd.DateOffset(months=month_offset)
    return date(month.year, month.month, day)


def stage_forecast_date(
    target_period: pd.Period | str,
    stage_code: str,
    release_date: date | None = None,
) -> date:
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="Q")
    )
    if stage_code == "early_quarter":
        return _month_date(period, 0)
    if stage_code == "after_month_1":
        return _month_date(period, 1)
    if stage_code == "after_month_2":
        return _month_date(period, 2)
    if stage_code == "quarter_end":
        return period.end_time.normalize().date()
    if stage_code == "pre_advance_release":
        if release_date is None:
            raise ValueError("pre_advance_release requires the initial GDP release date.")
        return release_date - timedelta(days=1)
    raise ValueError(f"Unknown forecast stage: {stage_code}")


def infer_forecast_stage(
    target_period: pd.Period | str,
    information_cutoff: date,
    release_date: date | None = None,
) -> str:
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="Q")
    )
    candidates: list[tuple[date, str]] = []
    for stage in FORECAST_STAGES:
        if stage.code == "pre_advance_release" and release_date is None:
            continue
        stage_date = stage_forecast_date(period, stage.code, release_date)
        if stage_date <= information_cutoff:
            candidates.append((stage_date, stage.code))
    if not candidates:
        return "quarter_open"
    return max(candidates, key=lambda item: item[0])[1]

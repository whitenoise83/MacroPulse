from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass(frozen=True)
class LabourForecastStage:
    code: str
    label: str
    description: str


LABOUR_FORECAST_STAGES: tuple[LabourForecastStage, ...] = (
    LabourForecastStage(
        "month_open",
        "Month open",
        "Information available on the first calendar day of the target month.",
    ),
    LabourForecastStage(
        "after_week_1",
        "After week 1",
        "Information available on the seventh calendar day of the target month.",
    ),
    LabourForecastStage(
        "after_week_2",
        "After week 2",
        "Information available on the fourteenth calendar day of the target month.",
    ),
    LabourForecastStage(
        "month_end",
        "Month end",
        "Information available at the end of the target month.",
    ),
    LabourForecastStage(
        "pre_employment_report",
        "Pre-employment report",
        "Information available one calendar day before the target's initial employment report release.",
    ),
)

LABOUR_STAGE_MAP = {stage.code: stage for stage in LABOUR_FORECAST_STAGES}


def validate_labour_stage_codes(stage_codes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    unknown = [code for code in stage_codes if code not in LABOUR_STAGE_MAP]
    if unknown:
        raise ValueError(
            f"Unknown labour forecast stages: {unknown}. "
            f"Valid stages are {sorted(LABOUR_STAGE_MAP)}."
        )
    return tuple(stage_codes)


def labour_stage_forecast_date(
    target_period: pd.Period | str,
    stage_code: str,
    release_date: date | None = None,
) -> date:
    period = target_period if isinstance(target_period, pd.Period) else pd.Period(target_period, freq="M")
    if stage_code == "month_open":
        return period.start_time.date()
    if stage_code == "after_week_1":
        return date(period.year, period.month, 7)
    if stage_code == "after_week_2":
        return date(period.year, period.month, 14)
    if stage_code == "month_end":
        return period.end_time.normalize().date()
    if stage_code == "pre_employment_report":
        if release_date is None:
            raise ValueError("pre_employment_report requires an initial release date.")
        return release_date - timedelta(days=1)
    raise ValueError(f"Unknown labour forecast stage: {stage_code}")


def infer_live_labour_stage(
    target_period: pd.Period | str,
    information_cutoff: date,
    release_date: date,
) -> str:
    """Return the latest predeclared labour stage reached by a live cutoff."""
    period = (
        target_period
        if isinstance(target_period, pd.Period)
        else pd.Period(target_period, freq="M")
    )
    schedule = [
        (labour_stage_forecast_date(period, "month_open", release_date), "month_open"),
        (labour_stage_forecast_date(period, "after_week_1", release_date), "after_week_1"),
        (labour_stage_forecast_date(period, "after_week_2", release_date), "after_week_2"),
        (labour_stage_forecast_date(period, "month_end", release_date), "month_end"),
        (labour_stage_forecast_date(period, "pre_employment_report", release_date), "pre_employment_report"),
    ]
    reached = [item for item in schedule if item[0] <= information_cutoff]
    if not reached:
        return "month_open"
    return max(reached, key=lambda item: item[0])[1]

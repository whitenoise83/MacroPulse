from datetime import date

import pandas as pd
import pytest

from macropulse.inflation.stages import (
    inflation_stage_forecast_date,
    validate_inflation_stage_codes,
)


def test_inflation_stage_dates_are_predeclared():
    period = pd.Period("2025-01", freq="M")
    release = date(2025, 2, 12)
    assert inflation_stage_forecast_date(period, "month_open", release) == date(2025, 1, 1)
    assert inflation_stage_forecast_date(period, "mid_month", release) == date(2025, 1, 15)
    assert inflation_stage_forecast_date(period, "month_end", release) == date(2025, 1, 31)
    assert inflation_stage_forecast_date(period, "pre_release", release) == date(2025, 2, 11)


def test_pre_release_requires_release_date():
    with pytest.raises(ValueError):
        inflation_stage_forecast_date("2025-01", "pre_release")


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError):
        validate_inflation_stage_codes(["month_end", "future_magic"])

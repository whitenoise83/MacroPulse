from datetime import date

import pandas as pd
import pytest

from macropulse.backtesting.stages import (
    infer_forecast_stage,
    stage_forecast_date,
    validate_stage_codes,
)


def test_stage_dates_are_deterministic() -> None:
    period = pd.Period("2024Q1", freq="Q")
    release = date(2024, 4, 25)
    assert stage_forecast_date(period, "early_quarter", release) == date(2024, 1, 15)
    assert stage_forecast_date(period, "after_month_1", release) == date(2024, 2, 15)
    assert stage_forecast_date(period, "after_month_2", release) == date(2024, 3, 15)
    assert stage_forecast_date(period, "quarter_end", release) == date(2024, 3, 31)
    assert stage_forecast_date(period, "pre_advance_release", release) == date(2024, 4, 24)


def test_infer_stage_uses_latest_completed_cutoff() -> None:
    period = pd.Period("2024Q1", freq="Q")
    release = date(2024, 4, 25)
    assert infer_forecast_stage(period, date(2024, 1, 10), release) == "quarter_open"
    assert infer_forecast_stage(period, date(2024, 2, 20), release) == "after_month_1"
    assert infer_forecast_stage(period, date(2024, 4, 24), release) == "pre_advance_release"


def test_unknown_stage_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_stage_codes(("quarter_end", "invented"))

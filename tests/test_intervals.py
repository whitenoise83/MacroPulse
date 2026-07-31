import pandas as pd

from macropulse.backtesting.intervals import empirical_interval_half_width


def _history(count: int) -> pd.DataFrame:
    dates = pd.date_range("2018-03-31", periods=count, freq="QE")
    return pd.DataFrame(
        {
            "model_name": ["Bridge Ridge"] * count,
            "forecast_stage": ["quarter_end"] * count,
            "forecast_date": dates,
            "point_forecast": [float(index) for index in range(count)],
            "actual": [float(index) + (index % 5) for index in range(count)],
        }
    )


def test_interval_falls_back_before_minimum_history() -> None:
    width, diagnostics = empirical_interval_half_width(
        _history(7), "Bridge Ridge", "quarter_end", min_history=8
    )
    assert width is None
    assert diagnostics["method"] == "model_interval_fallback"
    assert diagnostics["history_count"] == 7


def test_interval_uses_only_supplied_history() -> None:
    frame = _history(15)
    width, diagnostics = empirical_interval_half_width(
        frame, "Bridge Ridge", "quarter_end", coverage=0.80, window=12, min_history=8
    )
    assert width is not None
    assert diagnostics["method"] == "rolling_empirical_absolute_error"
    assert diagnostics["history_count"] == 12
    assert diagnostics["max_prior_forecast_date"] == frame["forecast_date"].max().date().isoformat()

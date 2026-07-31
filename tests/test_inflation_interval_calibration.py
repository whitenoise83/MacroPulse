from __future__ import annotations

import pandas as pd

from macropulse.inflation.interval_calibration import (
    calibrate_interval_frame,
    conformal_half_width,
)


def _base_frame(months: int = 40) -> pd.DataFrame:
    periods = pd.period_range("2020-01", periods=months, freq="M")
    rows = []
    for index, period in enumerate(periods):
        error = float((index % 5) + 1)
        point = 2.0
        actual = point + error
        rows.append(
            {
                "backtest_id": "bt",
                "target_series": "CPILFESL",
                "forecast_stage": "pre_release",
                "target_period": str(period),
                "model_name": "Inflation AR(1)",
                "point_forecast": point,
                "actual": actual,
                "abs_error": error,
            }
        )
    return pd.DataFrame(rows)


def test_conformal_half_width_uses_conservative_order_statistic() -> None:
    width = conformal_half_width([1, 2, 3, 4, 5], coverage=0.80)
    assert width == 5.0


def test_calibration_has_warmup_and_strict_prior_cutoff() -> None:
    calibrated = calibrate_interval_frame(
        _base_frame(),
        calibration_id="cal",
        minimum_prior_errors=24,
        rolling_window=36,
    )
    assert (calibrated.iloc[:24]["calibration_status"] == "warmup").all()
    assert calibrated.iloc[:24]["interval_covered"].isna().all()
    usable = calibrated.loc[calibrated["calibration_status"] == "calibrated"]
    assert len(usable) == 16
    for row in usable.itertuples(index=False):
        assert pd.Period(row.calibration_cutoff_period, freq="M") < pd.Period(
            row.target_period, freq="M"
        )
        assert row.prior_error_count >= 24


def test_current_error_does_not_change_its_own_interval() -> None:
    base = _base_frame()
    first = calibrate_interval_frame(
        base,
        calibration_id="cal1",
        minimum_prior_errors=24,
        rolling_window=48,
    )
    changed = base.copy()
    changed.loc[24, "abs_error"] = 10_000.0
    changed.loc[24, "actual"] = changed.loc[24, "point_forecast"] + 10_000.0
    second = calibrate_interval_frame(
        changed,
        calibration_id="cal2",
        minimum_prior_errors=24,
        rolling_window=48,
    )
    assert first.loc[24, "interval_half_width"] == second.loc[24, "interval_half_width"]
    assert second.loc[25, "interval_half_width"] >= first.loc[25, "interval_half_width"]

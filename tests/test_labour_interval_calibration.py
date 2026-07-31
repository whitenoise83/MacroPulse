from __future__ import annotations

import numpy as np
import pandas as pd

from macropulse.labour.interval_calibration import (
    calibrate_labour_interval_frame,
    interval_score,
    weighted_quantile,
)
from macropulse.labour.vintage import structural_missing_reason


def _sample_results(months: int = 36) -> pd.DataFrame:
    periods = pd.period_range("2019-01", periods=months, freq="M")
    errors = np.linspace(0.1, 3.6, months)
    return pd.DataFrame(
        {
            "backtest_id": "bt",
            "target_series": "UNRATE",
            "forecast_stage": "month_end",
            "target_period": periods.astype(str),
            "model_name": "Labour AR(1)",
            "point_forecast": np.repeat(4.0, months),
            "actual": 4.0 + errors,
            "abs_error": errors,
        }
    )


def test_weighted_quantile_prefers_recent_large_errors() -> None:
    values = [1.0, 2.0, 10.0]
    equal = weighted_quantile(values, [1.0, 1.0, 1.0], 0.8)
    recent = weighted_quantile(values, [0.01, 0.1, 1.0], 0.8)
    assert equal == 10.0
    assert recent == 10.0


def test_calibration_uses_strictly_prior_errors() -> None:
    calibrated = calibrate_labour_interval_frame(
        _sample_results(),
        calibration_id="cal",
        minimum_prior_errors=24,
        rolling_window=24,
        decay=0.94,
    )
    assert (calibrated.iloc[:24]["calibration_status"] == "warmup").all()
    usable = calibrated.loc[calibrated["calibration_status"] == "calibrated"]
    assert len(usable) == 12
    for row in usable.itertuples(index=False):
        assert pd.Period(row.calibration_cutoff_period, freq="M") < pd.Period(
            row.target_period, freq="M"
        )
        assert row.prior_error_count >= 24
        assert np.isfinite(row.interval_score)


def test_interval_score_penalises_miss() -> None:
    inside = interval_score(actual=0.0, lower=-1.0, upper=1.0, coverage=0.8)
    outside = interval_score(actual=2.0, lower=-1.0, upper=1.0, coverage=0.8)
    assert outside > inside


def test_october_2025_unrate_is_structurally_unavailable() -> None:
    reason = structural_missing_reason("UNRATE", pd.Period("2025-10", freq="M"))
    assert reason is not None
    assert structural_missing_reason("PAYEMS", pd.Period("2025-10", freq="M")) is None

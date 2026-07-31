import numpy as np
import pandas as pd

from macropulse.inflation.dataset import build_target_dataset


def _observations() -> pd.DataFrame:
    periods = pd.period_range("1985-01", periods=470, freq="M")
    series_ids = [
        "CPIAUCSL",
        "CPILFESL",
        "PCEPI",
        "PCEPILFE",
        "PPIFIS",
        "CES0500000003",
        "CUSR0000SEHA",
        "CUSR0000SEHC",
        "UNRATE",
        "FEDFUNDS",
        "T5YIE",
        "MICH",
        "DCOILWTICO",
    ]
    rows = []
    for offset, series_id in enumerate(series_ids):
        values = 100 * np.exp(np.arange(len(periods)) * (0.002 + offset * 0.00001))
        if series_id in {"UNRATE", "FEDFUNDS", "T5YIE", "MICH"}:
            values = 3.0 + 0.1 * np.sin(np.arange(len(periods)) / 12)
        for period, value in zip(periods, values):
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": period.start_time,
                    "value": value,
                    "realtime_start": period.start_time.date(),
                    "realtime_end": period.start_time.date(),
                    "retrieved_at": pd.Timestamp("2026-01-01"),
                }
            )
    return pd.DataFrame(rows)


def test_historical_target_period_restricts_training_sample():
    observations = _observations()
    target_period = pd.Period("2020-01", freq="M")
    dataset = build_target_dataset(observations, "CPILFESL", target_period=target_period)
    assert dataset.target_period == target_period
    assert dataset.y.index.max() < target_period
    assert dataset.forecast_X.index[0] == target_period

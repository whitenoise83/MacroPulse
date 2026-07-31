import numpy as np
import pandas as pd

from macropulse.inflation.dataset import build_target_dataset


def test_inflation_dataset_builds_monthly_forecast_row():
    periods = pd.period_range("1985-01", periods=500, freq="M")
    target_ids = ["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"]
    feature_ids = ["PPIFIS", "CES0500000003", "CUSR0000SEHA", "CUSR0000SEHC", "UNRATE", "FEDFUNDS", "MICH"]
    rows = []
    for j, series_id in enumerate(target_ids + feature_ids):
        start = 100 + j
        values = start * np.exp(np.arange(len(periods)) * (0.002 + j * 0.00001))
        if series_id in {"UNRATE", "FEDFUNDS", "MICH"}:
            values = 3.0 + 0.1 * np.sin(np.arange(len(periods)) / 12)
        for period, value in zip(periods, values):
            rows.append({"series_id": series_id, "observation_date": period.start_time, "value": value})
    daily = pd.date_range(periods[220].start_time, periods[-1].end_time, freq="B")
    for series_id, level in [("T5YIE", 2.2), ("DCOILWTICO", 70.0)]:
        for i, date in enumerate(daily):
            rows.append({"series_id": series_id, "observation_date": date, "value": level + 0.01 * np.sin(i / 20)})
    dataset = build_target_dataset(pd.DataFrame(rows), "CPILFESL")
    assert len(dataset.y) >= 120
    assert dataset.forecast_X.shape[0] == 1
    assert dataset.target_period == periods[-1] + 1

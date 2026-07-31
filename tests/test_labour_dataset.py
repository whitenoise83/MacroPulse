import numpy as np
import pandas as pd

from macropulse.labour.config import get_labour_series_definitions
from macropulse.labour.dataset import build_target_dataset


def synthetic_labour_observations() -> pd.DataFrame:
    months = pd.date_range("2000-01-01", "2026-06-01", freq="MS")
    rows = []
    for index, definition in enumerate(get_labour_series_definitions()):
        if definition.frequency == "W":
            dates = pd.date_range(months[0], months[-1] + pd.offsets.MonthEnd(0), freq="W-SAT")
            base = 200000 + 5000 * index
            values = base + 10000 * np.sin(np.arange(len(dates)) / 15.0) + np.arange(len(dates)) * 5
        else:
            dates = months
            if definition.series_id == "PAYEMS":
                values = 130000 + np.cumsum(150 + 20 * np.sin(np.arange(len(dates)) / 5.0))
            elif definition.series_id == "UNRATE":
                values = 5.0 + 0.5 * np.sin(np.arange(len(dates)) / 18.0)
            elif definition.series_id == "CES0500000003":
                values = 20.0 * np.exp(0.0025 * np.arange(len(dates)))
            else:
                values = 100 + index * 10 + 0.2 * np.arange(len(dates)) + 2 * np.sin(np.arange(len(dates)) / 8.0)
        for date, value in zip(dates, values):
            rows.append(
                {
                    "series_id": definition.series_id,
                    "observation_date": date,
                    "value": float(value),
                }
            )
    return pd.DataFrame(rows)


def test_build_payroll_dataset_respects_target_period():
    observations = synthetic_labour_observations()
    dataset = build_target_dataset(observations, "PAYEMS")
    assert dataset.target_period == pd.Period("2026-07", freq="M")
    assert dataset.X.index.max() < dataset.target_period
    assert dataset.forecast_X.index[0] == dataset.target_period
    assert len(dataset.y) >= 120
    assert dataset.target_unit == "thousands of jobs"


def test_build_unemployment_dataset_uses_level_target():
    observations = synthetic_labour_observations()
    dataset = build_target_dataset(observations, "UNRATE")
    assert dataset.target_transform == "level"
    assert 4.0 < dataset.latest_target_value < 6.0

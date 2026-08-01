import numpy as np
import pandas as pd

from macropulse.labour.config import get_labour_series_definitions
from macropulse.labour.live import estimate_target_models


def synthetic_labour_observations() -> pd.DataFrame:
    months = pd.date_range("2000-01-01", "2026-06-01", freq="MS")
    rows = []
    for index, definition in enumerate(get_labour_series_definitions()):
        if definition.frequency == "W":
            dates = pd.date_range(months[0], months[-1] + pd.offsets.MonthEnd(0), freq="W-SAT")
            values = 200000 + 5000 * index + 10000 * np.sin(np.arange(len(dates)) / 15.0)
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


def test_labour_model_suite_produces_fifteen_components():
    observations = synthetic_labour_observations()
    forecasts = []
    for target in ["PAYEMS", "UNRATE", "CES0500000003"]:
        _, models = estimate_target_models(observations, target)
        forecasts.extend((target, name, result.point_forecast) for name, result in models.items())
    assert len(forecasts) == 15
    assert {row[0] for row in forecasts} == {"PAYEMS", "UNRATE", "CES0500000003"}

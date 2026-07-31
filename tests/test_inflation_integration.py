import numpy as np
import pandas as pd

from macropulse.inflation.backtest import run_chronological_inflation_backtest
from macropulse.inflation.service import run_inflation_nowcast_suite


def _observations() -> pd.DataFrame:
    periods = pd.period_range("1985-01", periods=500, freq="M")
    targets = ["CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"]
    features = [
        "PPIFIS",
        "CES0500000003",
        "CUSR0000SEHA",
        "CUSR0000SEHC",
        "UNRATE",
        "FEDFUNDS",
        "MICH",
    ]
    rows = []
    for j, series_id in enumerate(targets + features):
        values = (100 + j) * np.exp(np.arange(len(periods)) * (0.002 + j * 0.00001))
        if series_id in {"UNRATE", "FEDFUNDS", "MICH"}:
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
    daily = pd.date_range(periods[220].start_time, periods[-1].end_time, freq="B")
    for series_id, level in [("T5YIE", 2.2), ("DCOILWTICO", 70.0)]:
        for i, day in enumerate(daily):
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": day,
                    "value": level + 0.01 * np.sin(i / 20),
                    "realtime_start": day.date(),
                    "realtime_end": day.date(),
                    "retrieved_at": pd.Timestamp("2026-01-01"),
                }
            )
    return pd.DataFrame(rows)


class _FakeRepository:
    def __init__(self):
        self.saved = None

    def initialise(self):
        return None

    def latest_observations(self):
        return _observations()

    def save_inflation_outputs(self, *frames):
        self.saved = frames

    def save_inflation_backtest_outputs(self, *frames):
        self.saved = frames


def test_live_inflation_suite_generates_four_targets_and_four_models():
    repository = _FakeRepository()
    result = run_inflation_nowcast_suite(repository)
    assert result["forecasts"].shape[0] == 16
    assert result["forecasts"]["target_series"].nunique() == 4
    assert result["forecasts"]["model_name"].nunique() == 4
    assert repository.saved is not None


def test_chronological_inflation_backtest_generates_results():
    repository = _FakeRepository()
    result = run_chronological_inflation_backtest(repository, start_date="2015-01")
    assert not result["results"].empty
    assert result["results"]["target_series"].nunique() == 4
    assert result["results"]["model_name"].nunique() == 4
    assert repository.saved is not None

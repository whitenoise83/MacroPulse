from datetime import date, timedelta

import numpy as np
import pandas as pd

from macropulse.inflation.vintage_backtest import run_vintage_inflation_backtest


SERIES_IDS = [
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


class _VintageRepository:
    def __init__(self):
        self.saved = None
        self.periods = pd.period_range("1985-01", "2015-03", freq="M")
        self.values = {}
        for offset, series_id in enumerate(SERIES_IDS):
            values = 100 * np.exp(
                np.arange(len(self.periods)) * (0.002 + offset * 0.00001)
            )
            if series_id in {"UNRATE", "FEDFUNDS", "T5YIE", "MICH"}:
                values = 3 + 0.1 * np.sin(np.arange(len(self.periods)) / 12)
            self.values[series_id] = dict(zip(self.periods, values))

    def initialise(self):
        return None

    def initial_release_date(self, series_id, target_period):
        return (target_period.end_time + pd.Timedelta(days=15)).date()

    def snapshot_is_cached(self, series_id, as_of_date):
        return True

    def historical_snapshot(self, as_of_date, series_ids=None):
        selected = series_ids or SERIES_IDS
        rows = []
        cutoff = pd.Timestamp(as_of_date)
        for series_id in selected:
            for period, value in self.values[series_id].items():
                if series_id in {"CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE"}:
                    available_date = period.end_time.normalize() + pd.Timedelta(days=15)
                else:
                    available_date = period.end_time.normalize() + pd.Timedelta(days=8)
                if available_date <= cutoff:
                    rows.append(
                        {
                            "series_id": series_id,
                            "observation_date": period.start_time,
                            "value": value,
                            "realtime_start": as_of_date,
                            "realtime_end": as_of_date,
                            "retrieved_at": pd.Timestamp("2026-01-01"),
                        }
                    )
        return pd.DataFrame(rows)

    def save_inflation_vintage_backtest_outputs(self, run, results):
        self.saved = (run, results)


class _UnusedClient:
    pass


def test_vintage_backtest_generates_four_models_for_each_stage():
    repository = _VintageRepository()
    result = run_vintage_inflation_backtest(
        repository=repository,
        client=_UnusedClient(),
        start_period="2015-01",
        end_period="2015-02",
        target_ids=["CPILFESL"],
        stage_codes=["month_open", "mid_month", "month_end", "pre_release"],
        pause_seconds=0,
    )
    assert result["status"] == "success"
    assert len(result["results"]) == 2 * 4 * 4
    assert result["results"]["model_name"].nunique() == 4
    assert result["results"]["forecast_stage"].nunique() == 4
    assert not result["results"]["target_leakage"].any()
    assert repository.saved is not None

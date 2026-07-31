from datetime import date

import numpy as np
import pandas as pd

from macropulse.labour.config import get_labour_series_definitions, target_definitions
from macropulse.labour.stages import labour_stage_forecast_date, validate_labour_stage_codes
from macropulse.labour.vintage import target_actual_from_release_snapshot
from macropulse.labour.vintage_backtest import run_vintage_labour_backtest


def test_labour_stage_dates_are_predeclared():
    period = pd.Period("2026-07", freq="M")
    release = date(2026, 8, 7)
    assert labour_stage_forecast_date(period, "month_open", release) == date(2026, 7, 1)
    assert labour_stage_forecast_date(period, "after_week_1", release) == date(2026, 7, 7)
    assert labour_stage_forecast_date(period, "after_week_2", release) == date(2026, 7, 14)
    assert labour_stage_forecast_date(period, "month_end", release) == date(2026, 7, 31)
    assert labour_stage_forecast_date(period, "pre_employment_report", release) == date(2026, 8, 6)
    assert validate_labour_stage_codes(["month_open", "pre_employment_report"]) == (
        "month_open", "pre_employment_report"
    )


def test_initial_release_payroll_change_uses_release_snapshot_levels():
    definition = next(item for item in target_definitions() if item.series_id == "PAYEMS")
    snapshot = pd.DataFrame({
        "series_id": ["PAYEMS", "PAYEMS"],
        "observation_date": [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-07-01")],
        "value": [160000.0, 160175.0],
    })
    actual = target_actual_from_release_snapshot(snapshot, definition, pd.Period("2026-07", freq="M"))
    assert actual == 175.0


SERIES_IDS = [item.series_id for item in get_labour_series_definitions()]


class _VintageRepository:
    def __init__(self):
        self.saved = None
        self.periods = pd.period_range("1985-01", "2018-03", freq="M")
        self.values = {}
        for offset, series_id in enumerate(SERIES_IDS):
            time = np.arange(len(self.periods), dtype=float)
            if series_id == "PAYEMS":
                values = 100000 + np.cumsum(150 + 10 * np.sin(time / 6))
            elif series_id == "UNRATE":
                values = 5 + 0.3 * np.sin(time / 18)
            elif series_id == "CES0500000003":
                values = 20 * np.exp(0.002 * time)
            elif series_id in {"ICSA", "CCSA"}:
                values = 200000 + offset * 1000 + 5000 * np.sin(time / 10)
            else:
                values = 100 + offset * 5 + 0.1 * time + np.sin(time / 8)
            self.values[series_id] = dict(zip(self.periods, values))

    def initialise(self):
        return None

    def initial_release_date(self, series_id, target_period):
        return (target_period.end_time.normalize() + pd.Timedelta(days=7)).date()

    def snapshot_is_cached(self, series_id, as_of_date):
        return True

    def historical_snapshot(self, as_of_date, series_ids=None):
        selected = series_ids or SERIES_IDS
        rows = []
        cutoff = pd.Timestamp(as_of_date)
        for series_id in selected:
            for period, value in self.values[series_id].items():
                if series_id in {"PAYEMS", "UNRATE", "CES0500000003"}:
                    available = period.end_time.normalize() + pd.Timedelta(days=7)
                else:
                    available = period.end_time.normalize()
                if available <= cutoff:
                    rows.append({
                        "series_id": series_id,
                        "observation_date": period.start_time,
                        "value": float(value),
                        "realtime_start": as_of_date,
                        "realtime_end": as_of_date,
                        "retrieved_at": pd.Timestamp("2026-01-01"),
                    })
        return pd.DataFrame(rows)

    def save_labour_vintage_backtest_outputs(self, run, results):
        self.saved = (run.copy(), results.copy())


class _UnusedClient:
    pass


def test_vintage_labour_backtest_generates_five_models_per_stage():
    repository = _VintageRepository()
    result = run_vintage_labour_backtest(
        repository=repository,
        client=_UnusedClient(),
        start_period="2018-01",
        end_period="2018-02",
        target_ids=["PAYEMS"],
        stage_codes=[
            "month_open", "after_week_1", "after_week_2", "month_end",
            "pre_employment_report",
        ],
        pause_seconds=0,
    )
    assert result["status"] == "success"
    assert len(result["results"]) == 2 * 5 * 5
    assert result["results"]["model_name"].nunique() == 5
    assert result["results"]["forecast_stage"].nunique() == 5
    assert (result["results"]["forecast_date"] < result["results"]["actual_release_date"]).all()
    assert repository.saved is not None

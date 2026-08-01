from __future__ import annotations

import json
import uuid
from datetime import date

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.labour.live import (
    governance_signature,
    live_interval_from_backtest,
    run_governed_labour_nowcast,
)
from macropulse.labour.operational_validation import run_labour_operational_validation
from macropulse.labour.policy import STABLE_POLICY
from macropulse.labour.stages import infer_live_labour_stage


MODELS = [
    "Labour Bridge Ridge",
    "Labour Factor Ridge",
    "Labour AR(1)",
    "Labour 12-Month Mean",
    "Labour Equal-Weight Ensemble",
]


def test_live_labour_stage_uses_latest_reached_stage() -> None:
    target = pd.Period("2026-07", freq="M")
    release = date(2026, 8, 7)
    assert infer_live_labour_stage(target, date(2026, 7, 1), release) == "month_open"
    assert infer_live_labour_stage(target, date(2026, 7, 8), release) == "after_week_1"
    assert infer_live_labour_stage(target, date(2026, 7, 20), release) == "after_week_2"
    assert infer_live_labour_stage(target, date(2026, 7, 31), release) == "month_end"
    assert infer_live_labour_stage(target, date(2026, 8, 6), release) == "pre_employment_report"


def test_live_labour_interval_is_prior_only() -> None:
    history = pd.DataFrame(
        {
            "target_period": [str(item) for item in pd.period_range("2020-01", periods=30, freq="M")],
            "abs_error": np.linspace(0.5, 3.0, 30),
        }
    )
    interval = live_interval_from_backtest(
        history,
        target_period="2022-07",
        point_forecast=2.0,
        minimum_prior_errors=24,
        rolling_window=24,
        decay=0.94,
    )
    assert interval.prior_error_count == 24
    assert pd.Period(interval.calibration_cutoff_period, freq="M") < pd.Period("2022-07", freq="M")
    assert interval.lower < 2.0 < interval.upper


def _seed_repository(repository: MacroRepository) -> None:
    repository.initialise()
    periods = pd.period_range("2005-01", "2026-06", freq="M")
    series_ids = [
        "PAYEMS", "UNRATE", "CES0500000003", "ICSA", "CCSA", "JTSJOL",
        "JTSQUR", "CIVPART", "EMRATIO", "TEMPHELPS", "AWHI", "MANEMP", "INDPRO",
    ]
    rows = []
    for series_index, series_id in enumerate(series_ids):
        for index, period in enumerate(periods):
            if series_id == "PAYEMS":
                value = 130000.0 + 150.0 * index + 20.0 * np.sin(index / 5)
            elif series_id == "UNRATE":
                value = 4.5 + 0.3 * np.sin(index / 12)
            elif series_id == "CES0500000003":
                value = 18.0 + 0.04 * index + 0.02 * np.sin(index / 7)
            elif series_id in {"CIVPART", "EMRATIO"}:
                value = 60.0 + 0.2 * np.sin(index / 10 + series_index)
            else:
                value = 100.0 + series_index * 5 + 0.2 * index + 0.5 * np.sin(index / 8)
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": period.start_time.date(),
                    "realtime_start": period.start_time.date(),
                    "realtime_end": date(9999, 12, 31),
                    "value": float(value),
                    "vintage_type": "latest",
                    "retrieved_at": pd.Timestamp("2026-07-31"),
                    "source": "FRED",
                }
            )
    repository.upsert_observations(pd.DataFrame(rows))

    initial_rows = []
    for target in STABLE_POLICY:
        for period in pd.period_range("2022-01", "2026-06", freq="M"):
            release = period.end_time.date() + pd.Timedelta(days=7)
            initial_rows.append(
                {
                    "series_id": target,
                    "observation_date": period.start_time.date(),
                    "realtime_start": pd.Timestamp(release).date(),
                    "realtime_end": date(9999, 12, 31),
                    "value": 100.0,
                    "vintage_type": "initial",
                    "retrieved_at": pd.Timestamp("2026-07-31"),
                    "source": "FRED",
                }
            )
    repository.upsert_observations(pd.DataFrame(initial_rows))

    backtest_id = str(uuid.uuid4())
    created_at = pd.Timestamp("2026-07-30")
    vintage_rows = []
    history_periods = pd.period_range("2019-01", "2026-06", freq="M")
    target_names = {
        "PAYEMS": ("Nonfarm Payroll Change", "thousands of jobs"),
        "UNRATE": ("Unemployment Rate", "percent"),
        "CES0500000003": ("Average Hourly Earnings Growth", "annualised percent"),
    }
    for target, stages in STABLE_POLICY.items():
        for stage, stable_model in stages.items():
            for index, period in enumerate(history_periods):
                actual = 2.0
                for model_index, model in enumerate(MODELS):
                    error = 0.4 + 0.03 * (index % 10) + 0.05 * model_index
                    if model == stable_model:
                        error *= 0.9
                    vintage_rows.append(
                        {
                            "backtest_id": backtest_id,
                            "target_series": target,
                            "target_name": target_names[target][0],
                            "target_unit": target_names[target][1],
                            "forecast_stage": stage,
                            "forecast_date": period.start_time.date(),
                            "target_period": str(period),
                            "actual_release_date": (period.end_time + pd.Timedelta(days=7)).date(),
                            "days_to_release": 7,
                            "model_name": model,
                            "point_forecast": actual - error,
                            "actual": actual,
                            "error": error,
                            "abs_error": abs(error),
                            "squared_error": error * error,
                            "direction_correct": True,
                            "lower_80": actual - 1.0,
                            "upper_80": actual + 1.0,
                            "interval_covered": True,
                            "training_observations": 150,
                            "imputed_feature_count": 0,
                            "information_set_hash": "a" * 64,
                            "target_leakage": False,
                            "max_observation_date": period.start_time.date(),
                            "regime": "post_2021",
                            "created_at": created_at,
                        }
                    )
    run_record = pd.DataFrame(
        [
            {
                "backtest_id": backtest_id,
                "model_id": "US_LABOUR_NOWCAST_1C",
                "model_version": "0.5.0",
                "created_at": created_at,
                "start_period": "2019-01",
                "end_period": "2026-06",
                "status": "success",
                "stage_codes_json": json.dumps(sorted(next(iter(STABLE_POLICY.values())))),
                "target_series_json": json.dumps(sorted(STABLE_POLICY)),
                "metrics_json": "{}",
                "notices_json": "[]",
                "notes": "synthetic",
            }
        ]
    )
    repository.save_labour_vintage_backtest_outputs(run_record, pd.DataFrame(vintage_rows))

    validation_id = str(uuid.uuid4())
    validation_run = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "backtest_id": backtest_id,
                "model_id": "US_LABOUR_NOWCAST_1C",
                "model_version": "0.5.0",
                "created_at": pd.Timestamp("2026-07-30 12:00:00"),
                "status": "pass",
                "passed_gates": 39,
                "failed_gates": 0,
                "warning_gates": 0,
                "report_path": "synthetic.md",
                "summary_json": json.dumps({"validation_type": "candidate_policy"}),
                "notes": "synthetic",
            }
        ]
    )
    repository.save_labour_validation_outputs(validation_run, pd.DataFrame())


def test_governed_labour_run_and_operational_validation(tmp_path) -> None:
    import duckdb
    import pytest

    probe = duckdb.connect(":memory:")
    if probe is None:
        pytest.skip("DuckDB is unavailable in this build environment.")
    probe.close()
    repository = MacroRepository(tmp_path / "live.duckdb")
    _seed_repository(repository)
    first = run_governed_labour_nowcast(
        repository, information_cutoff=date(2026, 7, 31)
    )
    assert len(first["forecasts"]) == 3
    assert len(first["governance_signature"]) == 64
    second = run_governed_labour_nowcast(
        repository, information_cutoff=date(2026, 7, 31)
    )
    assert second["news"]["status"] == "success"
    validation = run_labour_operational_validation(repository, second["run_id"])
    assert validation["status"] == "pass"
    assert validation["failed"] == 0


def test_governance_signature_changes_with_headline() -> None:
    run = {
        "run_id": "r",
        "model_id": "m",
        "model_version": "0.6.0",
        "candidate_validation_id": "v",
        "backtest_id": "b",
        "information_cutoff": date(2026, 7, 31),
        "information_set_hash": "a" * 64,
        "model_state_hash": "b" * 64,
        "config_hash": "c" * 64,
        "code_hash": "d" * 64,
        "git_commit": "g",
    }
    forecasts = pd.DataFrame(
        [
            {
                "target_series": "PAYEMS",
                "target_period": "2026-07",
                "forecast_stage": "month_end",
                "stable_model_name": "Labour Bridge Ridge",
                "stable_point_forecast": 100.0,
                "lower_80": 0.0,
                "upper_80": 200.0,
                "shadow_model_name": "Labour 12-Month Mean",
                "shadow_point_forecast": 90.0,
            }
        ]
    )
    original = governance_signature(run, forecasts)
    forecasts.loc[0, "stable_point_forecast"] = 101.0
    assert governance_signature(run, forecasts) != original


class _GovernedFakeRepository:
    def __init__(self, observations: pd.DataFrame, history: pd.DataFrame):
        self.observations = observations
        self.history = history
        self.validation_id = str(uuid.uuid4())
        self.backtest_id = str(history.iloc[0]["backtest_id"])
        self.live_run = None
        self.live_forecasts = None
        self.live_components = None
        self.saved_information_set = None

    def initialise(self):
        return None

    def register_model_identity(self, *args, **kwargs):
        return None

    def latest_observations(self, series_ids=None):
        frame = self.observations.copy()
        if series_ids:
            frame = frame.loc[frame["series_id"].isin(series_ids)]
        return frame

    def initial_release_date(self, target_series, target_period):
        return None

    def query_df(self, query, parameters=None):
        if "FROM labour_validation_runs" in query:
            return pd.DataFrame(
                [
                    {
                        "validation_id": self.validation_id,
                        "backtest_id": self.backtest_id,
                        "report_path": "candidate.md",
                        "passed_gates": 39,
                        "summary_json": json.dumps({"validation_type": "candidate_policy"}),
                        "created_at": pd.Timestamp("2026-07-30"),
                    }
                ]
            )
        if "FROM labour_vintage_backtest_results" in query:
            return self.history.copy()
        if "FROM observations" in query and "vintage_type = 'initial'" in query:
            periods = pd.period_range("2023-01", "2026-06", freq="M")
            return pd.DataFrame(
                {
                    "observation_date": [period.start_time.date() for period in periods],
                    "release_date": [
                        (period.end_time + pd.Timedelta(days=7)).date() for period in periods
                    ],
                }
            )
        raise AssertionError(query)

    def save_labour_outputs(self, *frames):
        self.legacy = frames

    def save_labour_live_outputs(self, run, forecasts, components):
        self.live_run = run.copy()
        self.live_forecasts = forecasts.copy()
        self.live_components = components.copy()

    def save_labour_live_information_set(self, run_id, observations):
        self.saved_information_set = observations.copy()
        return len(observations)


def _synthetic_observations_and_history():
    periods = pd.period_range("2005-01", "2026-06", freq="M")
    series_ids = [
        "PAYEMS", "UNRATE", "CES0500000003", "ICSA", "CCSA", "JTSJOL",
        "JTSQUR", "CIVPART", "EMRATIO", "TEMPHELPS", "AWHI", "MANEMP", "INDPRO",
    ]
    rows = []
    for series_index, series_id in enumerate(series_ids):
        for index, period in enumerate(periods):
            if series_id == "PAYEMS":
                value = 130000.0 + 150.0 * index + 20.0 * np.sin(index / 5)
            elif series_id == "UNRATE":
                value = 4.5 + 0.3 * np.sin(index / 12)
            elif series_id == "CES0500000003":
                value = 18.0 + 0.04 * index + 0.02 * np.sin(index / 7)
            elif series_id in {"CIVPART", "EMRATIO"}:
                value = 60.0 + 0.2 * np.sin(index / 10 + series_index)
            else:
                value = 100.0 + series_index * 5 + 0.2 * index + 0.5 * np.sin(index / 8)
            rows.append(
                {
                    "series_id": series_id,
                    "observation_date": period.start_time,
                    "value": value,
                    "realtime_start": period.start_time.date(),
                    "realtime_end": period.start_time.date(),
                    "retrieved_at": pd.Timestamp("2026-07-31"),
                }
            )
    backtest_id = str(uuid.uuid4())
    history_rows = []
    for target, stages in STABLE_POLICY.items():
        for stage, stable in stages.items():
            for index, period in enumerate(pd.period_range("2019-01", "2026-06", freq="M")):
                for model_index, model in enumerate(MODELS):
                    error = 0.5 + 0.02 * (index % 12) + 0.05 * model_index
                    if model == stable:
                        error *= 0.9
                    history_rows.append(
                        {
                            "backtest_id": backtest_id,
                            "target_series": target,
                            "forecast_stage": stage,
                            "target_period": str(period),
                            "model_name": model,
                            "point_forecast": 2.0 - error,
                            "error": error,
                            "abs_error": abs(error),
                            "direction_correct": True,
                        }
                    )
    return pd.DataFrame(rows), pd.DataFrame(history_rows)


def test_governed_labour_candidate_runs_with_fake_repository() -> None:
    observations, history = _synthetic_observations_and_history()
    repository = _GovernedFakeRepository(observations, history)
    result = run_governed_labour_nowcast(
        repository,
        information_cutoff=date(2026, 7, 31),
        build_news=False,
    )
    assert len(result["forecasts"]) == 3
    assert set(result["forecasts"]["forecast_stage"]) == {"month_end"}
    assert set(result["forecasts"]["interval_method"]) == {"exp_weighted_q80"}
    assert (result["forecasts"]["interval_prior_errors"] >= 24).all()
    assert repository.live_run is not None
    assert repository.live_components.shape[0] == 15
    assert len(result["governance_signature"]) == 64

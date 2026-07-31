from __future__ import annotations

import json
import uuid
from datetime import date

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.live import (
    governance_signature,
    live_interval_from_backtest,
    run_governed_inflation_nowcast,
)
from macropulse.inflation.operational_validation import (
    run_inflation_operational_validation,
)
from macropulse.inflation.policy import STABLE_POLICY
from macropulse.inflation.stages import infer_live_inflation_stage


MODELS = [
    "Inflation AR(1)",
    "Inflation 12-Month Mean",
    "Inflation Bridge Ridge",
    "Inflation Ridge-AR Ensemble",
]


def test_live_stage_uses_latest_reached_declared_stage() -> None:
    target = pd.Period("2026-07", freq="M")
    release = date(2026, 8, 14)
    assert infer_live_inflation_stage(target, date(2026, 7, 1), release) == "month_open"
    assert infer_live_inflation_stage(target, date(2026, 7, 20), release) == "mid_month"
    assert infer_live_inflation_stage(target, date(2026, 7, 31), release) == "month_end"
    assert infer_live_inflation_stage(target, date(2026, 8, 13), release) == "pre_release"


def test_live_interval_uses_only_prior_months() -> None:
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
    )
    assert interval.prior_error_count == 24
    assert pd.Period(interval.calibration_cutoff_period, freq="M") < pd.Period("2022-07", freq="M")
    assert interval.lower < 2.0 < interval.upper


def _seed_repository(repository: MacroRepository) -> None:
    repository.initialise()
    periods = pd.period_range("2009-01", "2026-06", freq="M")
    series_ids = [
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "PPIFIS",
        "CES0500000003", "CUSR0000SEHA", "CUSR0000SEHC", "UNRATE",
        "FEDFUNDS", "T5YIE", "MICH", "DCOILWTICO",
    ]
    rows = []
    for series_index, series_id in enumerate(series_ids):
        for index, period in enumerate(periods):
            if series_id in {"UNRATE", "FEDFUNDS", "T5YIE", "MICH"}:
                value = 2.0 + series_index * 0.1 + 0.2 * np.sin(index / 8)
            else:
                value = 80.0 + series_index * 5 + index * (0.15 + series_index * 0.002)
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
        lag = 14 if target in {"CPIAUCSL", "CPILFESL"} else 30
        for period in pd.period_range("2022-01", "2026-06", freq="M"):
            release = period.end_time.date() + pd.Timedelta(days=lag)
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
    history_periods = pd.period_range("2021-01", "2026-06", freq="M")
    for target, stages in STABLE_POLICY.items():
        for stage, stable_model in stages.items():
            for index, period in enumerate(history_periods):
                for model_index, model in enumerate(MODELS):
                    error = 0.4 + 0.03 * (index % 10) + 0.05 * model_index
                    if model == stable_model:
                        error *= 0.9
                    vintage_rows.append(
                        {
                            "backtest_id": backtest_id,
                            "target_series": target,
                            "forecast_stage": stage,
                            "forecast_date": period.start_time.date(),
                            "target_period": str(period),
                            "actual_release_date": (period.end_time + pd.Timedelta(days=30)).date(),
                            "days_to_release": 30,
                            "model_name": model,
                            "point_forecast": 2.0 - error,
                            "actual": 2.0,
                            "error": error,
                            "abs_error": abs(error),
                            "squared_error": error * error,
                            "lower_80": 1.0,
                            "upper_80": 3.0,
                            "interval_covered": True,
                            "imputed_feature_count": 0,
                            "information_set_hash": "a" * 64,
                            "max_observation_date": period.start_time.date(),
                            "training_observations": 150,
                            "target_leakage": False,
                            "created_at": created_at,
                        }
                    )
    run_record = pd.DataFrame(
        [
            {
                "backtest_id": backtest_id,
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "0.5.0",
                "created_at": created_at,
                "start_period": "2021-01",
                "end_period": "2026-06",
                "target_series_json": json.dumps(sorted(STABLE_POLICY)),
                "stages_json": json.dumps(sorted(next(iter(STABLE_POLICY.values())))),
                "status": "success",
                "config_json": "{}",
                "metrics_json": "{}",
                "notices_json": "[]",
                "notes": "synthetic",
            }
        ]
    )
    repository.save_inflation_vintage_backtest_outputs(run_record, pd.DataFrame(vintage_rows))

    validation_id = str(uuid.uuid4())
    validation_run = pd.DataFrame(
        [
            {
                "validation_id": validation_id,
                "model_id": "US_INFLATION_NOWCAST_1B",
                "model_version": "0.5.0",
                "backtest_id": backtest_id,
                "created_at": pd.Timestamp("2026-07-30 12:00:00"),
                "status": "pass",
                "passed_checks": 28,
                "failed_checks": 0,
                "warnings": 0,
                "report_path": "synthetic.md",
                "summary_json": json.dumps({"validation_type": "candidate_policy"}),
                "notes": "synthetic",
            }
        ]
    )
    repository.save_inflation_validation_outputs(validation_run, pd.DataFrame())


def test_governed_live_run_and_operational_validation(tmp_path) -> None:
    import duckdb
    probe = duckdb.connect(":memory:")
    if probe is None:
        import pytest
        pytest.skip("DuckDB is not installed in this build environment.")
    probe.close()
    repository = MacroRepository(tmp_path / "live.duckdb")
    _seed_repository(repository)
    first = run_governed_inflation_nowcast(
        repository,
        information_cutoff=date(2026, 7, 31),
    )
    assert len(first["forecasts"]) == 4
    assert len(first["governance_signature"]) == 64
    second = run_governed_inflation_nowcast(
        repository,
        information_cutoff=date(2026, 7, 31),
    )
    assert second["news"]["status"] == "success"
    validation = run_inflation_operational_validation(repository, second["run_id"])
    assert validation["status"] == "pass"
    assert validation["failed"] == 0


def test_governance_signature_is_sensitive_to_headline_change() -> None:
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
                "target_series": "CPIAUCSL",
                "target_period": "2026-07",
                "forecast_stage": "month_end",
                "stable_model_name": "Inflation Ridge-AR Ensemble",
                "stable_point_forecast": 2.0,
                "lower_80": 1.0,
                "upper_80": 3.0,
                "shadow_model_name": "Inflation Bridge Ridge",
                "shadow_point_forecast": 2.1,
            }
        ]
    )
    original = governance_signature(run, forecasts)
    forecasts.loc[0, "stable_point_forecast"] = 2.01
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
        if "FROM inflation_validation_runs" in query:
            return pd.DataFrame(
                [
                    {
                        "validation_id": self.validation_id,
                        "backtest_id": self.backtest_id,
                        "report_path": "candidate.md",
                        "passed_checks": 28,
                        "summary_json": json.dumps({"validation_type": "candidate_policy"}),
                        "created_at": pd.Timestamp("2026-07-30"),
                    }
                ]
            )
        if "FROM inflation_vintage_backtest_results" in query:
            return self.history.copy()
        if "FROM observations" in query and "vintage_type = 'initial'" in query:
            target = parameters[0]
            lag = 14 if target in {"CPIAUCSL", "CPILFESL"} else 30
            periods = pd.period_range("2024-01", "2026-06", freq="M")
            return pd.DataFrame(
                {
                    "observation_date": [period.start_time.date() for period in periods],
                    "release_date": [
                        (period.end_time + pd.Timedelta(days=lag)).date() for period in periods
                    ],
                }
            )
        raise AssertionError(query)

    def save_inflation_outputs(self, *frames):
        self.legacy = frames

    def save_inflation_live_outputs(self, run, forecasts, components):
        self.live_run = run.copy()
        self.live_forecasts = forecasts.copy()
        self.live_components = components.copy()

    def save_inflation_live_information_set(self, run_id, observations):
        self.saved_information_set = observations.copy()
        return len(observations)


def _synthetic_observations_and_history():
    periods = pd.period_range("2009-01", "2026-06", freq="M")
    series_ids = [
        "CPIAUCSL", "CPILFESL", "PCEPI", "PCEPILFE", "PPIFIS",
        "CES0500000003", "CUSR0000SEHA", "CUSR0000SEHC", "UNRATE",
        "FEDFUNDS", "T5YIE", "MICH", "DCOILWTICO",
    ]
    rows = []
    for series_index, series_id in enumerate(series_ids):
        for index, period in enumerate(periods):
            if series_id in {"UNRATE", "FEDFUNDS", "T5YIE", "MICH"}:
                value = 2.5 + 0.1 * np.sin(index / 8 + series_index)
            else:
                value = 90 + 4 * series_index + index * (0.18 + 0.001 * series_index)
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
            for index, period in enumerate(pd.period_range("2021-01", "2026-06", freq="M")):
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
                        }
                    )
    return pd.DataFrame(rows), pd.DataFrame(history_rows)


def test_governed_live_candidate_runs_with_in_memory_repository() -> None:
    observations, history = _synthetic_observations_and_history()
    repository = _GovernedFakeRepository(observations, history)
    result = run_governed_inflation_nowcast(
        repository,
        information_cutoff=date(2026, 7, 31),
        build_news=False,
    )
    assert len(result["forecasts"]) == 4
    assert set(result["forecasts"]["forecast_stage"]) == {"month_end"}
    assert set(result["forecasts"]["interval_method"]) == {"exp_weighted_q80"}
    assert (result["forecasts"]["interval_prior_errors"] >= 24).all()
    assert repository.live_run is not None
    assert repository.live_components.shape[0] == 16
    assert len(result["governance_signature"]) == 64

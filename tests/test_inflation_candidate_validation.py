from __future__ import annotations

import hashlib

import pandas as pd

from macropulse.inflation.candidate_validation import (
    CandidateValidationThresholds,
    evaluate_candidate_frames,
)
from macropulse.inflation.policy import SELECTED_INTERVAL_METHOD, STABLE_POLICY


MODELS = [
    "Inflation AR(1)",
    "Inflation 12-Month Mean",
    "Inflation Bridge Ridge",
    "Inflation Ridge-AR Ensemble",
]


def _synthetic_results(months: int = 40) -> pd.DataFrame:
    rows: list[dict] = []
    periods = pd.period_range("2020-01", periods=months, freq="M")
    for target, stage_map in STABLE_POLICY.items():
        for stage, stable_model in stage_map.items():
            for index, period in enumerate(periods):
                base = float((index % 5) + 1)
                sign = -1.0 if index % 2 else 1.0
                forecast_date = period.start_time
                release_date = forecast_date + pd.Timedelta(days=45)
                for model_index, model in enumerate(MODELS):
                    multiplier = 1.0 if model == stable_model else 1.15 + 0.05 * model_index
                    error = sign * base * multiplier
                    actual = 2.0
                    point = actual - error
                    digest = hashlib.sha256(
                        f"{target}|{stage}|{period}|{model}".encode()
                    ).hexdigest()
                    rows.append(
                        {
                            "backtest_id": "synthetic",
                            "target_series": target,
                            "forecast_stage": stage,
                            "forecast_date": forecast_date,
                            "target_period": str(period),
                            "actual_release_date": release_date,
                            "model_name": model,
                            "point_forecast": point,
                            "actual": actual,
                            "error": error,
                            "abs_error": abs(error),
                            "information_set_hash": digest,
                            "max_observation_date": forecast_date,
                            "training_observations": 180,
                            "target_leakage": False,
                        }
                    )
    return pd.DataFrame(rows)


def test_candidate_validation_reconstructs_predeclared_policy_and_intervals() -> None:
    thresholds = CandidateValidationThresholds(
        minimum_fixed_months_per_group=30,
        minimum_common_months_per_group=12,
        interval_aggregate_coverage_lower=0.0,
        interval_aggregate_coverage_upper=1.0,
        interval_group_coverage_lower=0.0,
        interval_group_coverage_upper=1.0,
        minimum_interval_months_per_group=12,
        maximum_shadow_switches_per_group=40,
        selected_interval_score_ratio=99.0,
    )
    result = evaluate_candidate_frames(_synthetic_results(), thresholds=thresholds)
    assert len(result["fixed"]) == 4 * 4 * 40
    assert set(result["selected_intervals"]["interval_method"]) == {
        SELECTED_INTERVAL_METHOD
    }
    assert not (result["checks"]["status"] == "fail").any()


def test_candidate_interval_cutoffs_are_strictly_prior() -> None:
    thresholds = CandidateValidationThresholds(
        minimum_fixed_months_per_group=30,
        minimum_common_months_per_group=12,
        interval_aggregate_coverage_lower=0.0,
        interval_aggregate_coverage_upper=1.0,
        interval_group_coverage_lower=0.0,
        interval_group_coverage_upper=1.0,
        minimum_interval_months_per_group=12,
        maximum_shadow_switches_per_group=40,
        selected_interval_score_ratio=99.0,
    )
    result = evaluate_candidate_frames(_synthetic_results(), thresholds=thresholds)
    intervals = result["selected_intervals"]
    assert all(
        pd.Period(cutoff, freq="M") < pd.Period(period, freq="M")
        for cutoff, period in zip(
            intervals["calibration_cutoff_period"], intervals["target_period"]
        )
    )

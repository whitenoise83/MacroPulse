from __future__ import annotations

import hashlib

import pandas as pd

from macropulse.labour.candidate_validation import (
    CandidateValidationThresholds,
    evaluate_candidate_frames,
)
from macropulse.labour.policy import SELECTED_INTERVAL_METHOD, STABLE_POLICY


MODELS = [
    "Labour AR(1)",
    "Labour 12-Month Mean",
    "Labour Bridge Ridge",
    "Labour Factor Ridge",
    "Labour Equal-Weight Ensemble",
]


def _synthetic_results(months: int = 60) -> pd.DataFrame:
    rows: list[dict] = []
    periods = pd.period_range("2017-01", periods=months, freq="M")
    for target, stage_map in STABLE_POLICY.items():
        for stage, stable_model in stage_map.items():
            for index, period in enumerate(periods):
                base = float((index % 5) + 1)
                sign = -1.0 if index % 2 else 1.0
                forecast_date = period.start_time
                release_date = forecast_date + pd.Timedelta(days=35)
                if index < 20:
                    regime = "pre_pandemic"
                elif index < 40:
                    regime = "pandemic_dislocation"
                else:
                    regime = "post_2021"
                for model_index, model in enumerate(MODELS):
                    multiplier = 1.0 if model == stable_model else 1.20 + 0.04 * model_index
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
                            "target_name": target,
                            "target_unit": "synthetic",
                            "forecast_stage": stage,
                            "forecast_date": forecast_date,
                            "target_period": str(period),
                            "actual_release_date": release_date,
                            "days_to_release": 35,
                            "model_name": model,
                            "point_forecast": point,
                            "actual": actual,
                            "error": error,
                            "abs_error": abs(error),
                            "squared_error": error**2,
                            "direction_correct": True,
                            "lower_80": point - 5.0,
                            "upper_80": point + 5.0,
                            "interval_covered": True,
                            "training_observations": 180,
                            "imputed_feature_count": 0,
                            "information_set_hash": digest,
                            "target_leakage": False,
                            "max_observation_date": forecast_date,
                            "regime": regime,
                        }
                    )
    return pd.DataFrame(rows)


def _synthetic_calibrated(results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for row in results.itertuples(index=False):
        period = pd.Period(row.target_period, freq="M")
        prior = period - 1
        index = period.ordinal - pd.Period("2017-01", freq="M").ordinal
        if index < 24:
            status = "warmup"
            covered = None
            half_width = None
            score = None
            prior_count = index
        else:
            status = "calibrated"
            covered = bool(index % 5 != 0)
            half_width = abs(float(row.error)) + 1.0
            score = half_width * 2.0
            prior_count = 24 + min(index - 24, 48)
        rows.append(
            {
                "calibration_id": "cal-synthetic",
                "backtest_id": "synthetic",
                "target_series": row.target_series,
                "forecast_stage": row.forecast_stage,
                "target_period": row.target_period,
                "model_name": row.model_name,
                "interval_method": SELECTED_INTERVAL_METHOD,
                "lower_80": row.point_forecast - half_width if half_width else None,
                "upper_80": row.point_forecast + half_width if half_width else None,
                "interval_covered": covered,
                "interval_half_width": half_width,
                "interval_score": score,
                "prior_error_count": prior_count,
                "calibration_window_count": min(prior_count, 48),
                "calibration_cutoff_period": str(prior),
                "calibration_status": status,
                "created_at": pd.Timestamp("2026-01-01"),
            }
        )
    return pd.DataFrame(rows)


def _thresholds() -> CandidateValidationThresholds:
    return CandidateValidationThresholds(
        minimum_fixed_months_per_group=50,
        minimum_common_months_per_group=30,
        minimum_interval_months_per_group=30,
        interval_aggregate_coverage_lower=0.0,
        interval_aggregate_coverage_upper=1.0,
        interval_group_coverage_lower=0.0,
        interval_group_coverage_upper=1.0,
        maximum_shadow_switches_per_group=60,
        minimum_regime_months=20,
    )


def test_candidate_validation_reconstructs_policy_and_prior_intervals() -> None:
    results = _synthetic_results()
    calibrated = _synthetic_calibrated(results)
    evaluated = evaluate_candidate_frames(
        results,
        calibrated,
        notices=[{"kind": "structural_missing", "target_period": "2025-10"}],
        base_validation_available=True,
        thresholds=_thresholds(),
    )
    assert len(evaluated["fixed"]) == 3 * 5 * 60
    assert set(evaluated["fixed_intervals"]["interval_method"]) == {
        SELECTED_INTERVAL_METHOD
    }
    assert not (evaluated["checks"]["status"] == "fail").any()


def test_candidate_interval_cutoffs_are_strictly_prior() -> None:
    results = _synthetic_results()
    calibrated = _synthetic_calibrated(results)
    evaluated = evaluate_candidate_frames(
        results,
        calibrated,
        base_validation_available=True,
        thresholds=_thresholds(),
    )
    intervals = evaluated["fixed_intervals"]
    assert all(
        pd.Period(cutoff, freq="M") < pd.Period(period, freq="M")
        for cutoff, period in zip(
            intervals["calibration_cutoff_period"], intervals["target_period"]
        )
    )

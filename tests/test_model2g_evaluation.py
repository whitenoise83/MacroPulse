from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from macropulse.bvar.benchmarks import (
    BENCHMARK_IDS,
    simulate_all_benchmarks,
)
from macropulse.bvar.evaluation import (
    OutcomeObservation,
    aggregate_metrics,
    canonical_frame_hash,
    derived_seed,
    empirical_crps,
    evaluate_origin,
    interval_score,
    kde_log_predictive_density,
    score_predictive_draws,
    select_bvar_candidate,
)
from macropulse.bvar.model import VARIABLES, candidate_grid


def synthetic_panel(periods: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(1234)
    values = np.zeros((periods, 4), dtype=float)
    values[0] = [2.0, 2.3, 4.8, 3.0]
    transition = np.array(
        [
            [0.30, 0.04, -0.01, -0.01],
            [0.03, 0.45, -0.02, 0.02],
            [-0.02, 0.01, 0.84, 0.01],
            [0.03, 0.07, -0.02, 0.75],
        ]
    )
    intercept = np.array([1.25, 1.10, 0.70, 0.75])
    noise = np.array([0.35, 0.30, 0.07, 0.10])
    for t in range(1, periods):
        values[t] = (
            intercept
            + transition @ values[t - 1]
            + rng.normal(scale=noise, size=4)
        )
    return pd.DataFrame(
        values,
        index=pd.period_range("1990Q1", periods=periods, freq="Q"),
        columns=list(VARIABLES),
    )


def outcomes() -> dict[int, OutcomeObservation]:
    base = np.array([2.1, 2.4, 4.2, 3.6], dtype=float)
    result = {}
    for horizon in (1, 2, 4, 8):
        result[horizon] = OutcomeObservation(
            horizon=horizon,
            target_quarter=str(pd.Period("2014Q4", freq="Q") + horizon),
            values=base + np.array(
                [0.05 * horizon, -0.02 * horizon, 0.01 * horizon, 0.03 * horizon]
            ),
            outcome_as_of_date=date(2017, 1, 15) + pd.Timedelta(days=100 * horizon),
            outcome_snapshot_hash=f"hash-{horizon}",
        )
    return result


def test_derived_seed_is_deterministic_and_model_specific() -> None:
    first = derived_seed(123, "origin", "model-a")
    second = derived_seed(123, "origin", "model-a")
    other = derived_seed(123, "origin", "model-b")
    assert first == second
    assert first != other
    assert 0 <= first < 2**63


def test_empirical_crps_is_zero_for_perfect_constant_draws() -> None:
    draws = np.ones(100)
    assert empirical_crps(draws, 1.0) == pytest.approx(0.0)


def test_log_density_prefers_nearby_outcome() -> None:
    draws = np.linspace(-1.0, 1.0, 500)
    near = kde_log_predictive_density(draws, 0.0)
    far = kde_log_predictive_density(draws, 10.0)
    assert near > far


def test_interval_score_penalises_miss() -> None:
    inside = interval_score(-1.0, 1.0, 0.0, 0.8)
    outside = interval_score(-1.0, 1.0, 3.0, 0.8)
    assert outside > inside


def test_score_error_sign_is_forecast_minus_outcome() -> None:
    scored = score_predictive_draws(
        point_forecast_value=3.0,
        draws=np.linspace(2.0, 4.0, 200),
        outcome=2.5,
    )
    assert scored["error"] == pytest.approx(0.5)
    assert scored["abs_error"] == pytest.approx(0.5)


def test_benchmark_suite_contains_three_models() -> None:
    panel = synthetic_panel()
    seeds = {model_id: i + 1 for i, model_id in enumerate(BENCHMARK_IDS)}
    forecasts = simulate_all_benchmarks(
        panel,
        horizons=(1, 2, 4, 8),
        simulations=100,
        seeds=seeds,
    )
    assert {item.model_id for item in forecasts} == set(BENCHMARK_IDS)
    for item in forecasts:
        assert item.point.shape == (4, 4)
        assert item.draws.shape == (100, 4, 4)
        assert np.isfinite(item.draws).all()


def test_evaluate_origin_is_common_case_for_nine_models() -> None:
    panel = synthetic_panel()
    result = evaluate_origin(
        panel,
        origin_id="origin-1",
        origin_quarter="2014Q4",
        origin_as_of_date=date(2017, 1, 1),
        outcomes=outcomes(),
        simulations=100,
        base_seed=20260904,
    )
    assert result["model_id"].nunique() == 9
    counts = result.groupby(["horizon", "variable"])["model_id"].nunique()
    assert bool((counts == 9).all())
    assert len(result) == 9 * 4 * 4


def test_evaluate_origin_contains_all_six_bvar_candidates() -> None:
    panel = synthetic_panel()
    result = evaluate_origin(
        panel,
        origin_id="origin-1",
        origin_quarter="2014Q4",
        origin_as_of_date=date(2017, 1, 1),
        outcomes=outcomes(),
        simulations=100,
        base_seed=20260904,
    )
    observed = set(
        result.loc[
            result["model_family"] == "bvar",
            "candidate_id",
        ].dropna()
    )
    assert observed == {candidate.candidate_id for candidate in candidate_grid()}


def test_outcome_before_origin_fails_closed() -> None:
    panel = synthetic_panel()
    bad = outcomes()
    bad[1] = OutcomeObservation(
        horizon=1,
        target_quarter="2015Q1",
        values=np.ones(4),
        outcome_as_of_date=date(2016, 1, 1),
        outcome_snapshot_hash="bad",
    )
    with pytest.raises(ValueError, match="later than forecast origin"):
        evaluate_origin(
            panel,
            origin_id="origin-1",
            origin_quarter="2014Q4",
            origin_as_of_date=date(2017, 1, 1),
            outcomes={1: bad[1]},
            simulations=100,
            base_seed=1,
        )


def test_aggregate_metrics_produces_expected_metric_columns() -> None:
    panel = synthetic_panel()
    records = evaluate_origin(
        panel,
        origin_id="origin-1",
        origin_quarter="2014Q4",
        origin_as_of_date=date(2017, 1, 1),
        outcomes=outcomes(),
        simulations=100,
        base_seed=1,
    )
    aggregate = aggregate_metrics(records)
    for column in (
        "bias", "mae", "rmse", "mean_log_predictive_density",
        "mean_crps", "coverage_50", "coverage_80", "coverage_95",
        "mean_interval_score_50", "mean_interval_score_80",
        "mean_interval_score_95",
    ):
        assert column in aggregate.columns
        assert np.isfinite(aggregate[column].to_numpy(dtype=float)).all()


def synthetic_selection_aggregate() -> pd.DataFrame:
    rows = []
    for candidate_index, candidate in enumerate(candidate_grid()):
        for variable in VARIABLES:
            for horizon in (1, 2, 4):
                rows.append(
                    {
                        "model_id": "bvar::" + candidate.candidate_id,
                        "model_family": "bvar",
                        "candidate_id": candidate.candidate_id,
                        "lags": candidate.lags,
                        "shrinkage": candidate.shrinkage,
                        "variable": variable,
                        "horizon": horizon,
                        "n": 10,
                        "bias": 0.0,
                        "mae": 1.0,
                        "rmse": 1.0 + candidate_index * 0.01,
                        "mean_log_predictive_density": -2.0 + candidate_index * 0.1,
                        "mean_crps": 1.0 - candidate_index * 0.01,
                        "coverage_50": 0.5,
                        "coverage_80": 0.8,
                        "coverage_95": 0.95,
                        "mean_interval_score_50": 1.0,
                        "mean_interval_score_80": 1.0,
                        "mean_interval_score_95": 1.0,
                    }
                )
    return pd.DataFrame.from_records(rows)


def test_selection_uses_highest_mean_log_density() -> None:
    table = select_bvar_candidate(synthetic_selection_aggregate())
    assert len(table) == 6
    assert bool(table.iloc[0]["selected"])
    assert table.iloc[0]["candidate_id"] == candidate_grid()[-1].candidate_id


def test_selection_rejects_insufficient_cell_count() -> None:
    aggregate = synthetic_selection_aggregate()
    aggregate.loc[0, "n"] = 7
    with pytest.raises(ValueError, match="insufficient resolved cases"):
        select_bvar_candidate(aggregate)


def test_selection_rejects_missing_candidate() -> None:
    aggregate = synthetic_selection_aggregate()
    missing_id = candidate_grid()[0].candidate_id
    aggregate = aggregate[aggregate["candidate_id"] != missing_id]
    with pytest.raises(ValueError, match="all six"):
        select_bvar_candidate(aggregate)


def test_frame_hash_is_row_order_invariant_when_sort_keys_are_supplied() -> None:
    frame = pd.DataFrame(
        {
            "model_id": ["b", "a"],
            "horizon": [2, 1],
            "value": [2.0, 1.0],
        }
    )
    first = canonical_frame_hash(
        frame,
        sort_columns=["model_id", "horizon"],
    )
    second = canonical_frame_hash(
        frame.iloc[::-1].reset_index(drop=True),
        sort_columns=["model_id", "horizon"],
    )
    assert first == second


def test_frame_hash_changes_when_value_changes() -> None:
    frame = pd.DataFrame(
        {"model_id": ["a"], "horizon": [1], "value": [1.0]}
    )
    first = canonical_frame_hash(
        frame,
        sort_columns=["model_id", "horizon"],
    )
    altered = frame.copy()
    altered.loc[0, "value"] = 2.0
    second = canonical_frame_hash(
        altered,
        sort_columns=["model_id", "horizon"],
    )
    assert first != second

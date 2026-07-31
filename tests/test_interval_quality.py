import pandas as pd

from macropulse.backtesting.metrics import coverage_test, interval_score


def test_41_of_45_is_not_rejected_against_80_percent_at_five_percent() -> None:
    covered = pd.Series([True] * 41 + [False] * 4)
    result = coverage_test(covered, target_coverage=0.80)
    assert result["coverage"] == 41 / 45
    assert result["p_value"] > 0.05


def test_interval_score_penalises_misses() -> None:
    actual = pd.Series([0.0, 3.0])
    lower = pd.Series([-1.0, -1.0])
    upper = pd.Series([1.0, 1.0])
    scores = interval_score(actual, lower, upper, coverage=0.80)
    assert scores.iloc[0] == 2.0
    assert scores.iloc[1] > scores.iloc[0]


def test_clustered_coverage_resamples_target_quarters() -> None:
    from macropulse.backtesting.metrics import clustered_coverage_test

    rows = []
    for quarter in range(20):
        actual = 1.0
        covered = quarter < 16
        for stage in range(5):
            rows.append(
                {
                    "target_period": f"Q{quarter}",
                    "forecast_stage": f"stage_{stage}",
                    "model_name": "Stable Stage Policy",
                    "actual": actual,
                    "lower_80": 0.0 if covered else 1.1,
                    "upper_80": 2.0 if covered else 1.2,
                }
            )
    result = clustered_coverage_test(
        pd.DataFrame(rows),
        model_name="Stable Stage Policy",
        bootstrap_samples=1000,
        random_seed=7,
    )
    assert result["clusters"] == 20
    assert result["forecasts"] == 100
    assert result["coverage"] == 0.8
    assert 0.0 <= result["p_value"] <= 1.0

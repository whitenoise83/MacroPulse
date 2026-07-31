from __future__ import annotations

import pandas as pd

from macropulse.inflation.policy import (
    STABLE_POLICY,
    ShadowSelectorConfig,
    compare_policies_on_common_sample,
    interval_tournament,
    policy_model,
    selected_interval_diagnostics,
    summarise_shadow_switching,
    select_fixed_policy,
    select_prior_only_shadow,
)


def _synthetic_results(months: int = 36) -> pd.DataFrame:
    rows = []
    periods = pd.period_range("2020-01", periods=months, freq="M")
    models = [
        "Inflation AR(1)",
        "Inflation 12-Month Mean",
        "Inflation Bridge Ridge",
        "Inflation Ridge-AR Ensemble",
    ]
    for period_index, period in enumerate(periods):
        for model_index, model in enumerate(models):
            error = float((model_index + 1) * 0.1 + (period_index % 5) * 0.01)
            rows.append(
                {
                    "backtest_id": "test",
                    "target_series": "CPIAUCSL",
                    "forecast_stage": "month_open",
                    "target_period": str(period),
                    "model_name": model,
                    "point_forecast": 2.0 - error,
                    "actual": 2.0,
                    "error": error,
                    "abs_error": abs(error),
                }
            )
    return pd.DataFrame(rows)


def test_stable_policy_contains_all_sixteen_target_stage_decisions() -> None:
    assert sum(len(stages) for stages in STABLE_POLICY.values()) == 16
    assert policy_model("CPILFESL", "month_open") == "Inflation 12-Month Mean"
    assert policy_model("PCEPI", "pre_release") == "Inflation Bridge Ridge"


def test_fixed_policy_selects_one_model_per_period() -> None:
    selected = select_fixed_policy(_synthetic_results())
    assert len(selected) == 36
    assert selected["model_name"].nunique() == 1
    assert selected["model_name"].iloc[0] == "Inflation Ridge-AR Ensemble"


def test_shadow_selector_uses_strictly_prior_periods() -> None:
    results = _synthetic_results(40)
    selected = select_prior_only_shadow(
        results,
        ShadowSelectorConfig(minimum_prior_errors=12, rolling_window=18),
    )
    usable = selected.loc[selected["prior_period_count"] >= 12]
    assert not usable.empty
    assert all(
        pd.Period(cutoff, freq="M") < pd.Period(period, freq="M")
        for cutoff, period in zip(usable["selection_cutoff_period"], usable["target_period"])
    )


def test_interval_tournament_is_prior_only() -> None:
    selected = select_fixed_policy(_synthetic_results(40))
    intervals = interval_tournament(
        selected,
        minimum_prior_errors=12,
        rolling_window=18,
    )
    assert set(intervals["interval_method"]) == {
        "rolling_q80",
        "exp_weighted_q80",
        "target_shrunk_q80",
        "ewma_gaussian",
    }
    assert all(
        pd.Period(cutoff, freq="M") < pd.Period(period, freq="M")
        for cutoff, period in zip(intervals["calibration_cutoff_period"], intervals["target_period"])
    )


def test_common_sample_comparison_uses_identical_months() -> None:
    results = _synthetic_results(40)
    fixed = select_fixed_policy(results)
    shadow = select_prior_only_shadow(
        results, ShadowSelectorConfig(minimum_prior_errors=12, rolling_window=18)
    )
    comparison, long_summary = compare_policies_on_common_sample(
        fixed, shadow, minimum_prior_errors=12
    )
    assert not comparison.empty
    pair = long_summary.pivot_table(
        index=["target_series", "forecast_stage"],
        columns="policy",
        values="observations",
    )
    assert (pair["stable_candidate"] == pair["adaptive_shadow"]).all()
    assert "shadow_to_fixed_rmse_ratio" in comparison.columns


def test_shadow_switching_summary_counts_only_eligible_months() -> None:
    results = _synthetic_results(40)
    shadow = select_prior_only_shadow(
        results, ShadowSelectorConfig(minimum_prior_errors=12, rolling_window=18)
    )
    summary = summarise_shadow_switching(shadow, minimum_prior_errors=12)
    assert not summary.empty
    assert int(summary.iloc[0]["eligible_months"]) == 28
    assert 0.0 <= float(summary.iloc[0]["stable_policy_share"]) <= 1.0


def test_selected_interval_diagnostics_returns_one_row_per_group() -> None:
    selected = select_fixed_policy(_synthetic_results(40))
    intervals = interval_tournament(selected, minimum_prior_errors=12, rolling_window=18)
    diagnostics = selected_interval_diagnostics(intervals)
    assert len(diagnostics) == 1
    assert diagnostics.iloc[0]["observations"] == 28

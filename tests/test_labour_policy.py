from __future__ import annotations

import pandas as pd

from macropulse.labour.policy import (
    STABLE_POLICY,
    ShadowSelectorConfig,
    attach_calibrated_intervals,
    compare_policies_on_common_sample,
    policy_model,
    select_fixed_policy,
    select_prior_only_shadow,
    summarise_intervals,
    summarise_regime_performance,
    summarise_shadow_switching,
)


MODELS = [
    "Labour AR(1)",
    "Labour 12-Month Mean",
    "Labour Bridge Ridge",
    "Labour Factor Ridge",
    "Labour Equal-Weight Ensemble",
]


def _synthetic_results(months: int = 40) -> pd.DataFrame:
    rows: list[dict] = []
    periods = pd.period_range("2018-01", periods=months, freq="M")
    for period_index, period in enumerate(periods):
        for model_index, model in enumerate(MODELS):
            # The stable month-open payroll component has a moderate error. The
            # bridge is materially better, allowing the prior-only selector to
            # switch only after the configured warm-up.
            if model == "Labour 12-Month Mean":
                error = 2.0 + (period_index % 3) * 0.05
            elif model == "Labour Bridge Ridge":
                error = 1.0 + (period_index % 3) * 0.02
            else:
                error = 3.0 + model_index * 0.2 + (period_index % 3) * 0.03
            rows.append(
                {
                    "backtest_id": "bt",
                    "target_series": "PAYEMS",
                    "forecast_stage": "month_open",
                    "target_period": str(period),
                    "model_name": model,
                    "point_forecast": 100.0 - error,
                    "actual": 100.0,
                    "error": error,
                    "abs_error": abs(error),
                    "direction_correct": model != "Labour Factor Ridge",
                    "regime": (
                        "pre_pandemic" if period < pd.Period("2020-03", freq="M")
                        else "pandemic_dislocation" if period < pd.Period("2021-01", freq="M")
                        else "post_2021"
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_stable_policy_contains_all_fifteen_decisions() -> None:
    assert sum(len(stages) for stages in STABLE_POLICY.values()) == 15
    assert policy_model("PAYEMS", "month_open") == "Labour 12-Month Mean"
    assert policy_model("UNRATE", "pre_employment_report") == "Labour Equal-Weight Ensemble"
    assert policy_model("CES0500000003", "after_week_1") == "Labour Bridge Ridge"


def test_fixed_policy_selects_one_model_per_month() -> None:
    fixed = select_fixed_policy(_synthetic_results())
    assert len(fixed) == 40
    assert fixed["model_name"].nunique() == 1
    assert fixed["model_name"].iloc[0] == "Labour 12-Month Mean"


def test_shadow_selection_is_strictly_prior_only() -> None:
    shadow = select_prior_only_shadow(
        _synthetic_results(),
        ShadowSelectorConfig(minimum_prior_errors=12, rolling_window=18),
    )
    usable = shadow.loc[shadow["prior_period_count"] >= 12]
    assert not usable.empty
    assert all(
        pd.Period(cutoff, freq="M") < pd.Period(period, freq="M")
        for cutoff, period in zip(usable["selection_cutoff_period"], usable["target_period"])
    )
    assert "Labour Bridge Ridge" in set(usable["selected_model"])


def test_common_sample_has_identical_observation_counts() -> None:
    results = _synthetic_results()
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
    assert "directional_accuracy_improved" in comparison.columns


def test_switching_summary_uses_only_eligible_months() -> None:
    shadow = select_prior_only_shadow(
        _synthetic_results(), ShadowSelectorConfig(minimum_prior_errors=12, rolling_window=18)
    )
    summary = summarise_shadow_switching(shadow, minimum_prior_errors=12)
    assert int(summary.iloc[0]["eligible_months"]) == 28
    assert int(summary.iloc[0]["distinct_selected_models"]) >= 1
    assert 0.0 <= float(summary.iloc[0]["stable_policy_share"]) <= 1.0


def test_calibrated_intervals_follow_selected_model() -> None:
    fixed = select_fixed_policy(_synthetic_results(30))
    rows = []
    for row in _synthetic_results(30).itertuples(index=False):
        rows.append(
            {
                "calibration_id": "cal",
                "target_series": row.target_series,
                "forecast_stage": row.forecast_stage,
                "target_period": row.target_period,
                "model_name": row.model_name,
                "interval_method": "exp_weighted_q80",
                "lower_80": row.point_forecast - 3.0,
                "upper_80": row.point_forecast + 3.0,
                "interval_covered": True,
                "interval_half_width": 3.0,
                "interval_score": 6.0,
                "prior_error_count": 24,
                "calibration_cutoff_period": "2019-12",
                "calibration_status": "calibrated",
            }
        )
    attached = attach_calibrated_intervals(fixed, pd.DataFrame(rows))
    summary = summarise_intervals(attached)
    assert len(attached) == 30
    assert len(summary) == 1
    assert float(summary.iloc[0]["coverage"]) == 1.0


def test_regime_summary_preserves_all_present_regimes() -> None:
    fixed = select_fixed_policy(_synthetic_results(40))
    summary = summarise_regime_performance(fixed)
    assert set(summary["regime"]) == {
        "pre_pandemic", "pandemic_dislocation", "post_2021"
    }

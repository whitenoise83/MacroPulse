import pandas as pd

from macropulse.backtesting.production_selection import (
    ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
    STABLE_STAGE_POLICY_NAME,
    build_stable_stage_policy,
    effective_bridge_dfm_weights,
    select_robust_stage_candidate,
)
from macropulse.models.baseline import ForecastResult


def _result(name: str, point: float) -> ForecastResult:
    return ForecastResult(
        model_name=name,
        point_forecast=point,
        lower=point - 1,
        upper=point + 1,
        sigma=1.0,
        fitted_values=pd.Series(dtype=float),
        coefficients=pd.Series(dtype=float),
    )


def _candidates() -> list[ForecastResult]:
    return [
        _result("Bridge Ridge", 1.0),
        _result("Dynamic Factor Model", 2.0),
        _result("Bridge–DFM Ensemble", 1.5),
        _result("Rolling Bridge–DFM Ensemble", 1.6),
    ]


def _history(periods: int = 24, dfm_error: float = 0.2) -> pd.DataFrame:
    rows = []
    dates = pd.date_range("2015-03-31", periods=periods, freq="QE")
    for index, forecast_date in enumerate(dates):
        actual = float(index % 5)
        for name, error in [
            ("Bridge Ridge", 1.0),
            ("Dynamic Factor Model", dfm_error),
            ("Bridge–DFM Ensemble", 0.7),
            ("Rolling Bridge–DFM Ensemble", 0.6),
        ]:
            rows.append(
                {
                    "forecast_date": forecast_date,
                    "target_period": str(pd.Period(forecast_date, freq="Q")),
                    "model_name": name,
                    "point_forecast": actual + error,
                    "actual": actual,
                }
            )
    return pd.DataFrame(rows)


def test_stable_stage_policy_uses_declared_component() -> None:
    policy, diagnostics = build_stable_stage_policy(
        _candidates(), forecast_stage="quarter_end"
    )
    assert policy.model_name == STABLE_STAGE_POLICY_NAME
    assert diagnostics["selected_component"] == "Rolling Bridge–DFM Ensemble"
    assert diagnostics["fallback_used"] is False


def test_robust_policy_uses_stable_incumbent_before_twenty_quarters() -> None:
    policy, diagnostics = select_robust_stage_candidate(
        _candidates(),
        _history(periods=12),
        forecast_stage="after_month_1",
        min_history=20,
    )
    assert policy.model_name == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    assert diagnostics["selected_component"] == "Dynamic Factor Model"
    assert diagnostics["method"] == "stable_incumbent_fallback"
    assert diagnostics["switched"] is False


def test_robust_policy_switches_only_for_material_guarded_improvement() -> None:
    policy, diagnostics = select_robust_stage_candidate(
        _candidates(),
        _history(periods=24, dfm_error=0.1),
        forecast_stage="quarter_end",
        incumbent_model="Rolling Bridge–DFM Ensemble",
        min_history=20,
        switch_threshold=0.05,
    )
    assert policy.model_name == ROBUST_STAGE_ADAPTIVE_MODEL_NAME
    assert diagnostics["selected_component"] == "Dynamic Factor Model"
    assert diagnostics["switched"] is True
    assert diagnostics["tail_guard_passed"] is True
    assert diagnostics["maximum_error_guard_passed"] is True


def test_effective_weights_represent_selected_candidate() -> None:
    assert effective_bridge_dfm_weights("Bridge Ridge") == {
        "Bridge Ridge": 1.0,
        "Dynamic Factor Model": 0.0,
    }
    assert effective_bridge_dfm_weights("Dynamic Factor Model") == {
        "Bridge Ridge": 0.0,
        "Dynamic Factor Model": 1.0,
    }
    weights = effective_bridge_dfm_weights(
        "Rolling Bridge–DFM Ensemble",
        {"Bridge Ridge": 0.4, "Dynamic Factor Model": 0.6},
    )
    assert weights == {"Bridge Ridge": 0.4, "Dynamic Factor Model": 0.6}

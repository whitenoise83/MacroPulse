import numpy as np
import pandas as pd

from macropulse.inflation.models import fit_ar1, fit_ridge_bridge


def test_inflation_models_produce_finite_forecasts():
    index = pd.period_range("2000-01", periods=160, freq="M")
    rng = np.random.default_rng(42)
    y = pd.Series(2.0 + rng.normal(0, 0.5, len(index)), index=index)
    X = pd.DataFrame({"lag": y.shift(1), "x": rng.normal(size=len(index))}, index=index).dropna()
    aligned_y = y.reindex(X.index)
    forecast_X = X.iloc[[-1]].copy()
    ridge = fit_ridge_bridge(X, aligned_y, forecast_X)
    ar = fit_ar1(y)
    assert np.isfinite(ridge.point_forecast)
    assert np.isfinite(ar.point_forecast)
    assert ridge.lower_80 <= ridge.point_forecast <= ridge.upper_80

import numpy as np
import pandas as pd

from macropulse.labour.models import fit_model_suite


def test_labour_model_suite_returns_five_models():
    rng = np.random.default_rng(42)
    index = pd.period_range("2008-01", periods=180, freq="M")
    X = pd.DataFrame(rng.normal(size=(180, 12)), index=index, columns=[f"x{i}" for i in range(12)])
    y = pd.Series(0.4 * X["x0"] - 0.2 * X["x1"] + rng.normal(scale=0.5, size=180), index=index)
    forecast_X = pd.DataFrame([rng.normal(size=12)], index=pd.period_range("2023-01", periods=1, freq="M"), columns=X.columns)
    results = fit_model_suite(
        X,
        y,
        forecast_X,
        {
            "interval_coverage": 0.8,
            "ridge_alpha": 10.0,
            "factor_ridge_alpha": 8.0,
            "factor_components": 4,
            "rolling_mean_window": 12,
        },
    )
    assert [result.model_name for result in results] == [
        "Labour Bridge Ridge",
        "Labour Factor Ridge",
        "Labour AR(1)",
        "Labour 12-Month Mean",
        "Labour Equal-Weight Ensemble",
    ]
    for result in results:
        assert np.isfinite(result.point_forecast)
        assert result.lower_80 <= result.point_forecast <= result.upper_80

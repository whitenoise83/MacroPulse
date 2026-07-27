from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.ar_model import AutoReg


@dataclass
class ForecastResult:
    model_name: str
    point_forecast: float
    lower: float
    upper: float
    sigma: float
    fitted_values: pd.Series
    coefficients: pd.Series


def _z_value(interval: float) -> float:
    if not 0.0 < interval < 1.0:
        raise ValueError("Prediction interval must be between 0 and 1.")
    return NormalDist().inv_cdf(0.5 + interval / 2.0)


def fit_bridge_ridge(
    training: pd.DataFrame,
    current_features: pd.DataFrame,
    alpha: float = 10.0,
    interval: float = 0.80,
) -> ForecastResult:
    feature_names = [column for column in training.columns if column != "target"]
    x_train = training[feature_names]
    y_train = training["target"]
    x_current = current_features[feature_names]

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=alpha)),
        ]
    )
    model.fit(x_train, y_train)

    fitted = pd.Series(model.predict(x_train), index=training.index, name="bridge")
    point = float(model.predict(x_current)[0])
    sigma = float(np.sqrt(np.mean(np.square(y_train - fitted))))
    z_value = _z_value(interval)

    scaler = model.named_steps["scaler"]
    ridge = model.named_steps["ridge"]
    standardised_coefficients = pd.Series(
        ridge.coef_, index=feature_names, name="coefficient"
    )
    # Coefficients are intentionally reported on the standardised feature scale,
    # which makes magnitudes comparable across predictors.
    standardised_coefficients.loc["intercept"] = float(ridge.intercept_)

    return ForecastResult(
        model_name="Bridge Ridge",
        point_forecast=point,
        lower=point - z_value * sigma,
        upper=point + z_value * sigma,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=standardised_coefficients,
    )


def fit_ar1(
    target: pd.Series,
    interval: float = 0.80,
) -> ForecastResult:
    clean_target = target.dropna().astype(float)
    model = AutoReg(clean_target, lags=1, trend="ct", old_names=False)
    result = model.fit()

    point = float(result.predict(start=len(clean_target), end=len(clean_target)).iloc[0])
    fitted = result.fittedvalues.rename("ar1")
    residuals = clean_target.loc[fitted.index] - fitted
    sigma = float(np.sqrt(np.mean(np.square(residuals))))
    z_value = _z_value(interval)

    coefficients = result.params.rename("coefficient")

    return ForecastResult(
        model_name="AR(1)",
        point_forecast=point,
        lower=point - z_value * sigma,
        upper=point + z_value * sigma,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=coefficients,
    )


def combine_equal_weight(
    bridge: ForecastResult,
    ar1: ForecastResult,
    interval: float = 0.80,
) -> ForecastResult:
    point = 0.5 * bridge.point_forecast + 0.5 * ar1.point_forecast
    sigma = float(np.sqrt(0.5 * bridge.sigma**2 + 0.5 * ar1.sigma**2))
    z_value = _z_value(interval)

    common_index = bridge.fitted_values.index.intersection(ar1.fitted_values.index)
    fitted = (
        0.5 * bridge.fitted_values.loc[common_index]
        + 0.5 * ar1.fitted_values.loc[common_index]
    )
    coefficients = pd.Series(
        {"Bridge Ridge weight": 0.5, "AR(1) weight": 0.5},
        name="coefficient",
    )

    return ForecastResult(
        model_name="Equal-weight Ensemble",
        point_forecast=point,
        lower=point - z_value * sigma,
        upper=point + z_value * sigma,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=coefficients,
    )

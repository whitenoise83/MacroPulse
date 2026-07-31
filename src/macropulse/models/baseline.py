from __future__ import annotations

from dataclasses import dataclass, field
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
    diagnostics: dict = field(default_factory=dict)


@dataclass
class BridgeFit:
    forecast: ForecastResult
    pipeline: Pipeline
    feature_names: list[str]
    training: pd.DataFrame
    current_features: pd.DataFrame

    def predict_features(self, features: pd.DataFrame) -> float:
        aligned = features[self.feature_names]
        return float(self.pipeline.predict(aligned)[0])

    def feature_contributions(
        self,
        previous_features: pd.DataFrame,
        updated_features: pd.DataFrame,
    ) -> pd.Series:
        """Exact fixed-parameter contributions to the Bridge forecast change."""
        previous = previous_features[self.feature_names].iloc[0].astype(float)
        updated = updated_features[self.feature_names].iloc[0].astype(float)
        scaler: StandardScaler = self.pipeline.named_steps["scaler"]
        ridge: Ridge = self.pipeline.named_steps["ridge"]
        scale = pd.Series(scaler.scale_, index=self.feature_names, dtype=float)
        coefficients = pd.Series(ridge.coef_, index=self.feature_names, dtype=float)
        contributions = coefficients * (updated - previous) / scale
        contributions.name = "impact"
        return contributions


def _z_value(interval: float) -> float:
    if not 0.0 < interval < 1.0:
        raise ValueError("Prediction interval must be between 0 and 1.")
    return NormalDist().inv_cdf(0.5 + interval / 2.0)


def estimate_bridge_ridge(
    training: pd.DataFrame,
    current_features: pd.DataFrame,
    alpha: float = 10.0,
    interval: float = 0.80,
) -> BridgeFit:
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

    ridge = model.named_steps["ridge"]
    standardised_coefficients = pd.Series(
        ridge.coef_, index=feature_names, name="coefficient"
    )
    standardised_coefficients.loc["intercept"] = float(ridge.intercept_)

    forecast = ForecastResult(
        model_name="Bridge Ridge",
        point_forecast=point,
        lower=point - z_value * sigma,
        upper=point + z_value * sigma,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=standardised_coefficients,
    )
    return BridgeFit(
        forecast=forecast,
        pipeline=model,
        feature_names=feature_names,
        training=training.copy(),
        current_features=current_features.copy(),
    )


def fit_bridge_ridge(
    training: pd.DataFrame,
    current_features: pd.DataFrame,
    alpha: float = 10.0,
    interval: float = 0.80,
) -> ForecastResult:
    return estimate_bridge_ridge(
        training=training,
        current_features=current_features,
        alpha=alpha,
        interval=interval,
    ).forecast


def fit_ar1(
    target: pd.Series,
    interval: float = 0.80,
) -> ForecastResult:
    clean_target = target.dropna().astype(float)
    model = AutoReg(clean_target, lags=1, trend="ct", old_names=False)
    result = model.fit()

    prediction = result.predict(start=len(clean_target), end=len(clean_target))
    point = float(prediction.iloc[0] if hasattr(prediction, "iloc") else prediction[0])
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


def combine_weighted(
    results: list[ForecastResult],
    weights: dict[str, float],
    model_name: str,
    interval: float = 0.80,
    diagnostics: dict | None = None,
) -> ForecastResult:
    """Combine forecasts with explicit non-negative weights.

    The interval uses the weighted mean of component residual variances. This is
    conservative because no diversification benefit from correlated model errors
    is assumed.
    """
    if not results:
        raise ValueError("At least one forecast result is required.")

    names = [result.model_name for result in results]
    missing = [name for name in names if name not in weights]
    extra = [name for name in weights if name not in names]
    if missing or extra:
        raise ValueError(
            f"Weights do not match component models. Missing={missing}, extra={extra}."
        )

    raw = np.array([float(weights[name]) for name in names], dtype=float)
    if not np.isfinite(raw).all() or (raw < 0).any() or raw.sum() <= 0:
        raise ValueError("Forecast weights must be finite, non-negative, and sum above zero.")
    normalised = raw / raw.sum()

    point = float(
        sum(weight * result.point_forecast for weight, result in zip(normalised, results))
    )
    sigma = float(
        np.sqrt(
            sum(weight * result.sigma**2 for weight, result in zip(normalised, results))
        )
    )
    z_value = _z_value(interval)

    common_index = results[0].fitted_values.index
    for result in results[1:]:
        common_index = common_index.intersection(result.fitted_values.index)

    if len(common_index):
        fitted = sum(
            weight * result.fitted_values.loc[common_index]
            for weight, result in zip(normalised, results)
        )
        fitted.name = model_name
    else:
        fitted = pd.Series(dtype=float, name=model_name)

    weight_map = {
        result.model_name: float(weight)
        for result, weight in zip(results, normalised)
    }
    coefficients = pd.Series(
        {f"{name} weight": weight for name, weight in weight_map.items()},
        name="coefficient",
    )
    result_diagnostics = {
        "component_models": names,
        "weights": weight_map,
    }
    if diagnostics:
        result_diagnostics.update(diagnostics)

    return ForecastResult(
        model_name=model_name,
        point_forecast=point,
        lower=point - z_value * sigma,
        upper=point + z_value * sigma,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=coefficients,
        diagnostics=result_diagnostics,
    )


def combine_equal_weight(
    bridge: ForecastResult,
    ar1: ForecastResult,
    interval: float = 0.80,
) -> ForecastResult:
    return combine_weighted(
        [bridge, ar1],
        {bridge.model_name: 0.5, ar1.model_name: 0.5},
        model_name="Equal-weight Ensemble",
        interval=interval,
    )


def combine_equal_weight_many(
    results: list[ForecastResult],
    model_name: str = "Equal-weight Model Suite",
    interval: float = 0.80,
) -> ForecastResult:
    if not results:
        raise ValueError("At least one forecast result is required.")
    weights = {result.model_name: 1.0 / len(results) for result in results}
    return combine_weighted(
        results=results,
        weights=weights,
        model_name=model_name,
        interval=interval,
        diagnostics={"weight_method": "equal"},
    )

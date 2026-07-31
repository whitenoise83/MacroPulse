from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class InflationModelResult:
    model_name: str
    point_forecast: float
    lower_80: float
    upper_80: float
    residuals: pd.Series
    coefficients: dict[str, float]
    diagnostics: dict


def _interval(point: float, residuals: pd.Series, coverage: float) -> tuple[float, float, float]:
    clean = pd.to_numeric(residuals, errors="coerce").dropna().abs()
    if clean.empty:
        width = 0.0
    else:
        width = float(clean.quantile(coverage))
    return point - width, point + width, width


def fit_ar1(y: pd.Series, forecast_value: float | None = None, coverage: float = 0.80) -> InflationModelResult:
    clean = pd.to_numeric(y, errors="coerce").dropna().astype(float)
    if len(clean) < 24:
        raise ValueError("AR(1) requires at least 24 observations.")
    lagged = clean.shift(1)
    frame = pd.concat([clean.rename("y"), lagged.rename("lag")], axis=1).dropna()
    design = np.column_stack([np.ones(len(frame)), frame["lag"].to_numpy()])
    beta, *_ = np.linalg.lstsq(design, frame["y"].to_numpy(), rcond=None)
    fitted = pd.Series(design @ beta, index=frame.index)
    residuals = frame["y"] - fitted
    previous = float(clean.iloc[-1] if forecast_value is None else forecast_value)
    point = float(beta[0] + beta[1] * previous)
    lower, upper, width = _interval(point, residuals, coverage)
    return InflationModelResult(
        model_name="Inflation AR(1)",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients={"intercept": float(beta[0]), "lag_1": float(beta[1])},
        diagnostics={"observations": len(frame), "interval_half_width": width},
    )


def fit_rolling_mean(y: pd.Series, window: int = 12, coverage: float = 0.80) -> InflationModelResult:
    clean = pd.to_numeric(y, errors="coerce").dropna().astype(float)
    if len(clean) < window + 12:
        raise ValueError("Rolling mean benchmark has insufficient observations.")
    fitted = clean.shift(1).rolling(window).mean().dropna()
    actual = clean.reindex(fitted.index)
    residuals = actual - fitted
    point = float(clean.iloc[-window:].mean())
    lower, upper, width = _interval(point, residuals, coverage)
    return InflationModelResult(
        model_name="Inflation 12-Month Mean",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients={},
        diagnostics={"observations": len(residuals), "window": window, "interval_half_width": width},
    )


def fit_ridge_bridge(
    X: pd.DataFrame,
    y: pd.Series,
    forecast_X: pd.DataFrame,
    alpha: float = 8.0,
    coverage: float = 0.80,
) -> InflationModelResult:
    aligned = X.join(y.rename("target"), how="inner").dropna()
    if len(aligned) < 60:
        raise ValueError("Inflation Bridge Ridge requires at least 60 complete observations.")
    train_X = aligned.drop(columns="target")
    train_y = aligned["target"]
    model = Pipeline([
        ("scale", StandardScaler()),
        ("ridge", Ridge(alpha=float(alpha))),
    ])
    model.fit(train_X, train_y)
    fitted = pd.Series(model.predict(train_X), index=train_X.index)
    residuals = train_y - fitted
    point = float(model.predict(forecast_X[train_X.columns])[0])
    lower, upper, width = _interval(point, residuals, coverage)
    ridge = model.named_steps["ridge"]
    coefficients = {name: float(value) for name, value in zip(train_X.columns, ridge.coef_)}
    coefficients["intercept_standardised"] = float(ridge.intercept_)
    return InflationModelResult(
        model_name="Inflation Bridge Ridge",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients=coefficients,
        diagnostics={
            "observations": len(train_X),
            "features": len(train_X.columns),
            "alpha": float(alpha),
            "interval_half_width": width,
        },
    )


def combine_equal_weight(
    first: InflationModelResult,
    second: InflationModelResult,
    y: pd.Series,
    coverage: float = 0.80,
) -> InflationModelResult:
    common = first.residuals.index.intersection(second.residuals.index)
    if len(common) >= 12:
        ensemble_residuals = 0.5 * first.residuals.loc[common] + 0.5 * second.residuals.loc[common]
    else:
        ensemble_residuals = pd.concat([first.residuals, second.residuals]).dropna()
    point = 0.5 * first.point_forecast + 0.5 * second.point_forecast
    lower, upper, width = _interval(point, ensemble_residuals, coverage)
    return InflationModelResult(
        model_name="Inflation Ridge-AR Ensemble",
        point_forecast=float(point),
        lower_80=lower,
        upper_80=upper,
        residuals=ensemble_residuals,
        coefficients={},
        diagnostics={
            "weights": {first.model_name: 0.5, second.model_name: 0.5},
            "interval_half_width": width,
        },
    )

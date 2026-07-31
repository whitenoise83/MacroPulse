from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class LabourModelResult:
    model_name: str
    point_forecast: float
    lower_80: float
    upper_80: float
    residuals: pd.Series
    coefficients: dict[str, float]
    diagnostics: dict


def _interval(point: float, residuals: pd.Series, coverage: float) -> tuple[float, float, float]:
    clean = pd.to_numeric(residuals, errors="coerce").dropna().abs()
    width = float(clean.quantile(coverage)) if not clean.empty else 0.0
    return point - width, point + width, width


def fit_ar1(
    y: pd.Series,
    forecast_value: float | None = None,
    coverage: float = 0.80,
) -> LabourModelResult:
    clean = pd.to_numeric(y, errors="coerce").dropna().astype(float)
    if len(clean) < 24:
        raise ValueError("Labour AR(1) requires at least 24 observations.")
    frame = pd.concat(
        [clean.rename("y"), clean.shift(1).rename("lag")], axis=1
    ).dropna()
    design = np.column_stack([np.ones(len(frame)), frame["lag"].to_numpy()])
    beta, *_ = np.linalg.lstsq(design, frame["y"].to_numpy(), rcond=None)
    fitted = pd.Series(design @ beta, index=frame.index)
    residuals = frame["y"] - fitted
    previous = float(clean.iloc[-1] if forecast_value is None else forecast_value)
    point = float(beta[0] + beta[1] * previous)
    lower, upper, width = _interval(point, residuals, coverage)
    return LabourModelResult(
        model_name="Labour AR(1)",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients={"intercept": float(beta[0]), "lag_1": float(beta[1])},
        diagnostics={"observations": len(frame), "interval_half_width": width},
    )


def fit_rolling_mean(
    y: pd.Series,
    window: int = 12,
    coverage: float = 0.80,
) -> LabourModelResult:
    clean = pd.to_numeric(y, errors="coerce").dropna().astype(float)
    if len(clean) < window + 12:
        raise ValueError("Labour rolling mean benchmark has insufficient observations.")
    fitted = clean.shift(1).rolling(window).mean().dropna()
    residuals = clean.reindex(fitted.index) - fitted
    point = float(clean.iloc[-window:].mean())
    lower, upper, width = _interval(point, residuals, coverage)
    return LabourModelResult(
        model_name="Labour 12-Month Mean",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients={},
        diagnostics={
            "observations": len(residuals),
            "window": window,
            "interval_half_width": width,
        },
    )


def fit_bridge_ridge(
    X: pd.DataFrame,
    y: pd.Series,
    forecast_X: pd.DataFrame,
    alpha: float = 10.0,
    coverage: float = 0.80,
) -> LabourModelResult:
    aligned = X.join(y.rename("target"), how="inner").dropna()
    if len(aligned) < 60:
        raise ValueError("Labour Bridge Ridge requires at least 60 complete observations.")
    train_X = aligned.drop(columns="target")
    train_y = aligned["target"]
    model = Pipeline(
        [("scale", StandardScaler()), ("ridge", Ridge(alpha=float(alpha)))]
    )
    model.fit(train_X, train_y)
    fitted = pd.Series(model.predict(train_X), index=train_X.index)
    residuals = train_y - fitted
    point = float(model.predict(forecast_X[train_X.columns])[0])
    lower, upper, width = _interval(point, residuals, coverage)
    ridge = model.named_steps["ridge"]
    coefficients = {
        name: float(value) for name, value in zip(train_X.columns, ridge.coef_)
    }
    coefficients["intercept_standardised"] = float(ridge.intercept_)
    return LabourModelResult(
        model_name="Labour Bridge Ridge",
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


def fit_factor_ridge(
    X: pd.DataFrame,
    y: pd.Series,
    forecast_X: pd.DataFrame,
    alpha: float = 8.0,
    components: int = 4,
    coverage: float = 0.80,
) -> LabourModelResult:
    aligned = X.join(y.rename("target"), how="inner").dropna()
    if len(aligned) < 60:
        raise ValueError("Labour Factor Ridge requires at least 60 complete observations.")
    train_X = aligned.drop(columns="target")
    train_y = aligned["target"]
    component_count = max(1, min(int(components), train_X.shape[1], len(train_X) - 1))
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("pca", PCA(n_components=component_count)),
            ("ridge", Ridge(alpha=float(alpha))),
        ]
    )
    model.fit(train_X, train_y)
    fitted = pd.Series(model.predict(train_X), index=train_X.index)
    residuals = train_y - fitted
    point = float(model.predict(forecast_X[train_X.columns])[0])
    lower, upper, width = _interval(point, residuals, coverage)
    ridge = model.named_steps["ridge"]
    pca = model.named_steps["pca"]
    coefficients = {
        f"factor_{index + 1}": float(value)
        for index, value in enumerate(ridge.coef_)
    }
    coefficients["intercept_factor_space"] = float(ridge.intercept_)
    return LabourModelResult(
        model_name="Labour Factor Ridge",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients=coefficients,
        diagnostics={
            "observations": len(train_X),
            "features": len(train_X.columns),
            "components": component_count,
            "explained_variance_ratio": [
                float(value) for value in pca.explained_variance_ratio_
            ],
            "alpha": float(alpha),
            "interval_half_width": width,
        },
    )


def combine_equal_weight(
    members: list[LabourModelResult],
    coverage: float = 0.80,
) -> LabourModelResult:
    if not members:
        raise ValueError("At least one model is required for the labour ensemble.")
    common = members[0].residuals.index
    for member in members[1:]:
        common = common.intersection(member.residuals.index)
    if len(common) >= 12:
        residuals = sum(member.residuals.loc[common] for member in members) / len(members)
    else:
        residuals = pd.concat([member.residuals for member in members]).dropna()
    point = float(np.mean([member.point_forecast for member in members]))
    lower, upper, width = _interval(point, residuals, coverage)
    weight = 1.0 / len(members)
    return LabourModelResult(
        model_name="Labour Equal-Weight Ensemble",
        point_forecast=point,
        lower_80=lower,
        upper_80=upper,
        residuals=residuals,
        coefficients={},
        diagnostics={
            "weights": {member.model_name: weight for member in members},
            "interval_half_width": width,
        },
    )


def fit_model_suite(
    X: pd.DataFrame,
    y: pd.Series,
    forecast_X: pd.DataFrame,
    config: dict,
) -> list[LabourModelResult]:
    coverage = float(config.get("interval_coverage", 0.80))
    bridge = fit_bridge_ridge(
        X,
        y,
        forecast_X,
        alpha=float(config.get("ridge_alpha", 10.0)),
        coverage=coverage,
    )
    ar1 = fit_ar1(y, coverage=coverage)
    mean = fit_rolling_mean(
        y,
        window=int(config.get("rolling_mean_window", 12)),
        coverage=coverage,
    )
    factor = fit_factor_ridge(
        X,
        y,
        forecast_X,
        alpha=float(config.get("factor_ridge_alpha", 8.0)),
        components=int(config.get("factor_components", 4)),
        coverage=coverage,
    )
    ensemble = combine_equal_weight([bridge, ar1, factor], coverage=coverage)
    return [bridge, factor, ar1, mean, ensemble]

from __future__ import annotations

import warnings
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.dynamic_factor_mq import DynamicFactorMQ
from statsmodels.tsa.statespace.dynamic_factor_mq import DynamicFactorMQResults

from macropulse.models.baseline import ForecastResult
from macropulse.processing.mixed_frequency import MixedFrequencyDataset


@dataclass
class DynamicFactorFit:
    forecast: ForecastResult
    results: DynamicFactorMQResults
    dataset: MixedFrequencyDataset


def _convergence_diagnostics(
    mle_retvals: dict,
    maxiter: int,
    tolerance: float,
) -> tuple[int, float | None, bool]:
    iterations = int(mle_retvals.get("iter", 0) or 0)
    llf_values = np.asarray(mle_retvals.get("llf", []), dtype=float)
    criterion: float | None = None
    if len(llf_values) >= 2:
        denominator = abs(llf_values[-1]) + abs(llf_values[-2])
        if denominator > 0:
            criterion = float(
                2.0 * abs(llf_values[-1] - llf_values[-2]) / denominator
            )
    converged = bool(
        criterion is not None
        and np.isfinite(criterion)
        and criterion <= tolerance
        and iterations <= maxiter
    )
    return iterations, criterion, converged


def _prediction_interval(
    prediction,
    target_name: str,
    interval: float,
) -> tuple[float, float, float, float]:
    alpha = 1.0 - interval
    mean = prediction.predicted_mean
    if isinstance(mean, pd.Series):
        point = float(mean.loc[target_name])
    else:
        point = float(mean[target_name].iloc[-1])

    confidence = prediction.conf_int(alpha=alpha)
    lower_column = f"lower {target_name}"
    upper_column = f"upper {target_name}"
    if lower_column not in confidence.columns or upper_column not in confidence.columns:
        lower_candidates = [
            column
            for column in confidence.columns
            if str(column).lower().startswith("lower")
            and target_name.lower() in str(column).lower()
        ]
        upper_candidates = [
            column
            for column in confidence.columns
            if str(column).lower().startswith("upper")
            and target_name.lower() in str(column).lower()
        ]
        if not lower_candidates or not upper_candidates:
            raise ValueError("Could not identify the Dynamic Factor forecast interval.")
        lower_column = lower_candidates[0]
        upper_column = upper_candidates[0]

    lower = float(confidence[lower_column].iloc[-1])
    upper = float(confidence[upper_column].iloc[-1])
    z_value = NormalDist().inv_cdf(0.5 + interval / 2.0)
    sigma = float((upper - lower) / (2.0 * z_value))
    return point, lower, upper, sigma


def estimate_dynamic_factor(
    dataset: MixedFrequencyDataset,
    interval: float = 0.80,
    factors: int = 1,
    factor_orders: int = 1,
    idiosyncratic_ar1: bool = True,
    maxiter: int = 100,
    tolerance: float = 1e-4,
    require_convergence: bool = False,
) -> DynamicFactorFit:
    """Estimate a mixed-frequency Dynamic Factor Model with EM."""
    if not 0.0 < interval < 1.0:
        raise ValueError("Prediction interval must be between 0 and 1.")

    monthly = dataset.monthly_features.copy()
    quarterly = dataset.quarterly_target.rename(dataset.target_name).copy()
    target_month = dataset.target_period.asfreq("M", how="end")

    if target_month not in monthly.index:
        raise ValueError(f"Target month {target_month} is not in the monthly dataset.")
    if pd.notna(quarterly.loc[dataset.target_period]):
        raise ValueError("The target quarter must be missing in the DFM dataset.")

    captured_warnings: list[str] = []
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")
        model = DynamicFactorMQ(
            monthly,
            endog_quarterly=quarterly.to_frame(),
            factors=factors,
            factor_orders=factor_orders,
            idiosyncratic_ar1=idiosyncratic_ar1,
            standardize=True,
        )
        result = model.fit(
            method="em",
            maxiter=maxiter,
            tolerance=tolerance,
            disp=False,
            full_output=True,
            llf_decrease_action="revert",
        )
        captured_warnings = [str(item.message) for item in warning_records]

    iterations, criterion, converged = _convergence_diagnostics(
        result.mle_retvals,
        maxiter=maxiter,
        tolerance=tolerance,
    )
    if require_convergence and not converged:
        raise RuntimeError(
            "Dynamic Factor EM estimation did not meet the configured "
            f"convergence tolerance ({criterion!r} > {tolerance})."
        )

    prediction = result.get_prediction(start=target_month, end=target_month)
    point, lower, upper, sigma = _prediction_interval(
        prediction,
        target_name=dataset.target_name,
        interval=interval,
    )
    if not all(np.isfinite(value) for value in [point, lower, upper, sigma]):
        raise RuntimeError("Dynamic Factor Model returned a non-finite forecast.")

    predicted = result.predict()
    target_prediction = predicted[dataset.target_name]
    quarter_end_mask = target_prediction.index.month.isin([3, 6, 9, 12])
    fitted = target_prediction.loc[quarter_end_mask].copy()
    fitted.index = fitted.index.asfreq("Q")
    fitted = fitted.groupby(level=0).last()
    fitted = fitted.loc[fitted.index < dataset.target_period]
    fitted.name = "dynamic_factor"

    coefficients = result.params.astype(float).rename("coefficient")
    log_likelihood = float(result.llf) if np.isfinite(result.llf) else None
    diagnostics = {
        "converged": converged,
        "iterations": iterations,
        "convergence_criterion": criterion,
        "tolerance": tolerance,
        "maximum_iterations": maxiter,
        "log_likelihood": log_likelihood,
        "monthly_observations": int(len(monthly)),
        "observed_gdp_quarters": int(quarterly.notna().sum()),
        "monthly_feature_count": int(monthly.shape[1]),
        "factor_count": int(factors),
        "factor_order": int(factor_orders),
        "idiosyncratic_ar1": bool(idiosyncratic_ar1),
        "target_month": str(target_month),
        "warnings": captured_warnings,
        "last_available_periods": dataset.last_available_periods,
    }

    forecast = ForecastResult(
        model_name="Dynamic Factor Model",
        point_forecast=point,
        lower=lower,
        upper=upper,
        sigma=sigma,
        fitted_values=fitted,
        coefficients=coefficients,
        diagnostics=diagnostics,
    )
    return DynamicFactorFit(forecast=forecast, results=result, dataset=dataset)


def fit_dynamic_factor(
    dataset: MixedFrequencyDataset,
    interval: float = 0.80,
    factors: int = 1,
    factor_orders: int = 1,
    idiosyncratic_ar1: bool = True,
    maxiter: int = 100,
    tolerance: float = 1e-4,
    require_convergence: bool = False,
) -> ForecastResult:
    return estimate_dynamic_factor(
        dataset=dataset,
        interval=interval,
        factors=factors,
        factor_orders=factor_orders,
        idiosyncratic_ar1=idiosyncratic_ar1,
        maxiter=maxiter,
        tolerance=tolerance,
        require_convergence=require_convergence,
    ).forecast

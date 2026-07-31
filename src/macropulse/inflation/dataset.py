from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macropulse.inflation.config import (
    InflationSeriesDefinition,
    feature_definitions,
    get_inflation_model_config,
    target_definitions,
)
from macropulse.processing.transforms import transform_series


@dataclass
class InflationDataset:
    target_series: str
    target_name: str
    X: pd.DataFrame
    y: pd.Series
    forecast_X: pd.DataFrame
    target_period: pd.Period
    latest_index_value: float
    latest_observed_period: pd.Period
    latest_mom_annualised: float
    latest_three_month_annualised: float
    latest_yoy: float
    feature_ages: dict[str, int]
    imputed_features: list[str]


def _monthly_series(frame: pd.DataFrame, definition: InflationSeriesDefinition) -> pd.Series:
    subset = frame.loc[frame["series_id"] == definition.series_id].copy()
    if subset.empty:
        return pd.Series(dtype=float, name=definition.series_id)
    subset["observation_date"] = pd.to_datetime(subset["observation_date"])
    subset = subset.sort_values("observation_date").drop_duplicates(
        "observation_date", keep="last"
    )
    series = pd.Series(
        pd.to_numeric(subset["value"], errors="coerce").to_numpy(),
        index=subset["observation_date"],
        name=definition.series_id,
    ).dropna()
    if definition.frequency.upper() == "D":
        if definition.monthly_aggregation == "mean":
            series = series.resample("MS").mean()
        else:
            series = series.resample("MS").last()
    else:
        series.index = series.index.to_period("M").to_timestamp()
        series = series.groupby(series.index).last()
    series.index = series.index.to_period("M")
    return series.sort_index()


def build_monthly_levels(observations: pd.DataFrame) -> pd.DataFrame:
    definitions = target_definitions() + feature_definitions()
    pieces = [_monthly_series(observations, definition) for definition in definitions]
    nonempty = [series for series in pieces if not series.empty]
    if not nonempty:
        return pd.DataFrame()
    return pd.concat(nonempty, axis=1).sort_index()


def _latest_at_or_before(series: pd.Series, period: pd.Period) -> tuple[float, int]:
    available = series.loc[series.index <= period].dropna()
    if available.empty:
        return np.nan, 10_000
    latest_period = available.index[-1]
    age = int(period.ordinal - latest_period.ordinal)
    return float(available.iloc[-1]), age


def build_target_dataset(
    observations: pd.DataFrame,
    target_series: str,
    target_period: pd.Period | str | None = None,
) -> InflationDataset:
    """Build a live or historical information-set inflation dataset.

    When ``target_period`` is omitted, the function forecasts the month after the
    latest observed target value. During vintage backtesting a specific period is
    supplied, and all training observations are restricted to months before that
    target period.
    """
    target_map = {item.series_id: item for item in target_definitions()}
    if target_series not in target_map:
        raise ValueError(f"Unknown inflation target: {target_series}")
    target_definition = target_map[target_series]
    config = get_inflation_model_config()
    levels = build_monthly_levels(observations)
    if target_series not in levels:
        raise ValueError(f"No observations are available for {target_series}.")

    transformed: dict[str, pd.Series] = {}
    definitions = target_definitions() + feature_definitions()
    definition_map = {item.series_id: item for item in definitions}
    for series_id in levels.columns:
        transformed[series_id] = transform_series(
            levels[series_id], definition_map[series_id].transform
        )
    panel = pd.DataFrame(transformed).sort_index()

    target = panel[target_series].dropna()
    latest_period = levels[target_series].dropna().index[-1]
    requested_period = (
        latest_period + 1
        if target_period is None
        else (
            target_period
            if isinstance(target_period, pd.Period)
            else pd.Period(target_period, freq="M")
        )
    )

    features = pd.DataFrame(index=panel.index)
    for lag in [int(item) for item in config.get("target_lags", [1, 2, 3, 6, 12])]:
        features[f"{target_series}_lag_{lag}"] = panel[target_series].shift(lag)
    for definition in feature_definitions():
        if definition.series_id not in panel:
            continue
        for lag in [int(item) for item in config.get("feature_lags", [1, 2])]:
            features[f"{definition.series_id}_lag_{lag}"] = panel[
                definition.series_id
            ].shift(lag)
    month_number = pd.Series(features.index.month, index=features.index, dtype=float)
    features["month_sin"] = np.sin(2.0 * np.pi * month_number / 12.0)
    features["month_cos"] = np.cos(2.0 * np.pi * month_number / 12.0)

    supervised = features.join(target.rename("target"), how="inner").dropna()
    supervised = supervised.loc[supervised.index < requested_period]
    if supervised.empty:
        raise ValueError(f"No complete modelling observations are available for {target_series}.")
    X = supervised.drop(columns="target")
    y = supervised["target"]

    forecast_row: dict[str, float] = {}
    feature_ages: dict[str, int] = {}
    imputed: list[str] = []
    max_carry = int(config.get("max_feature_carry_months", 2))
    for column in X.columns:
        if column == "month_sin":
            forecast_row[column] = float(
                np.sin(2.0 * np.pi * requested_period.month / 12.0)
            )
            continue
        if column == "month_cos":
            forecast_row[column] = float(
                np.cos(2.0 * np.pi * requested_period.month / 12.0)
            )
            continue
        series_id, lag_text = column.rsplit("_lag_", 1)
        source_period = requested_period - int(lag_text)
        value, age = _latest_at_or_before(panel[series_id], source_period)
        if not np.isfinite(value):
            raise ValueError(f"No usable value exists for forecast feature {column}.")
        forecast_row[column] = value
        feature_ages[column] = age
        if age > 0:
            imputed.append(column)
        if age > max_carry:
            raise ValueError(
                f"Forecast feature {column} is {age} months stale; maximum allowed is {max_carry}."
            )
    forecast_X = pd.DataFrame(
        [forecast_row], index=pd.PeriodIndex([requested_period], freq="M")
    )

    target_levels = levels[target_series].dropna()
    annualised = transform_series(target_levels, "annualised_mom_log")
    three_month = transform_series(target_levels, "three_month_annualised_log")
    yoy = transform_series(target_levels, "yoy_log_pct")
    return InflationDataset(
        target_series=target_series,
        target_name=target_definition.name,
        X=X,
        y=y,
        forecast_X=forecast_X[X.columns],
        target_period=requested_period,
        latest_index_value=float(target_levels.iloc[-1]),
        latest_observed_period=latest_period,
        latest_mom_annualised=float(annualised.dropna().iloc[-1]),
        latest_three_month_annualised=float(three_month.dropna().iloc[-1]),
        latest_yoy=float(yoy.dropna().iloc[-1]),
        feature_ages=feature_ages,
        imputed_features=sorted(imputed),
    )

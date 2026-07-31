from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from macropulse.config import SeriesDefinition
from macropulse.processing.transforms import transform_series


@dataclass
class MixedFrequencyDataset:
    target_name: str
    target_period: pd.Period
    monthly_features: pd.DataFrame
    quarterly_target: pd.Series
    feature_names: list[str]
    data_as_of: pd.Timestamp
    last_available_periods: dict[str, str | None]


def _series_from_observations(
    observations: pd.DataFrame,
    series_id: str,
) -> pd.Series:
    frame = observations.loc[observations["series_id"] == series_id]
    if frame.empty:
        return pd.Series(dtype=float, name=series_id)

    values = (
        frame.assign(observation_date=pd.to_datetime(frame["observation_date"]))
        .sort_values("observation_date")
        .drop_duplicates("observation_date", keep="last")
        .set_index("observation_date")["value"]
        .astype(float)
    )
    values.name = series_id
    return values


def build_mixed_frequency_dataset(
    observations: pd.DataFrame,
    definitions: list[SeriesDefinition],
    target_series: str,
    target_period: pd.Period | str | None = None,
    data_as_of: pd.Timestamp | None = None,
    minimum_months: int = 96,
    minimum_quarters: int = 24,
) -> MixedFrequencyDataset:
    """Build a ragged-edge monthly/quarterly dataset for DynamicFactorMQ.

    Monthly indicators remain at their native frequency and missing observations
    are preserved. The quarterly target is explicitly masked in the forecast
    quarter, preventing an already-released value from accidentally becoming an
    explanatory observation in a rerun.
    """
    if observations.empty:
        raise ValueError("No observations are available. Run the download script first.")

    observations = observations.copy()
    observations["observation_date"] = pd.to_datetime(
        observations["observation_date"]
    )
    definition_map = {definition.series_id: definition for definition in definitions}
    if target_series not in definition_map:
        raise KeyError(f"Target series {target_series} is not in the registry.")

    target_definition = definition_map[target_series]
    target_raw = _series_from_observations(observations, target_series)
    if target_raw.empty:
        raise ValueError(f"No observations were found for target {target_series}.")

    target_growth = transform_series(target_raw, target_definition.transform)
    target_growth.index = target_growth.index.to_period("Q")
    target_growth = target_growth.groupby(level=0).last().sort_index()
    target_growth.name = target_series

    monthly_series: list[pd.Series] = []
    last_available_periods: dict[str, str | None] = {}
    first_valid_periods: list[pd.Period] = []

    for definition in definitions:
        if definition.role != "feature" or definition.frequency.upper() != "M":
            continue

        raw = _series_from_observations(observations, definition.series_id)
        if raw.empty:
            last_available_periods[definition.series_id] = None
            continue

        transformed = transform_series(raw, definition.transform)
        transformed.index = transformed.index.to_period("M")
        transformed = transformed.groupby(level=0).last().sort_index()
        transformed.name = definition.series_id

        valid = transformed.dropna()
        if len(valid) < minimum_months:
            continue
        if not np.isfinite(valid.std()) or np.isclose(valid.std(), 0.0):
            continue

        monthly_series.append(transformed)
        first_valid_periods.append(valid.index.min())
        last_available_periods[definition.series_id] = str(valid.index.max())

    if len(monthly_series) < 3:
        raise ValueError(
            "Dynamic Factor Model requires at least three usable monthly indicators."
        )

    last_target_period = target_growth.dropna().index.max()
    last_feature_month = max(series.dropna().index.max() for series in monthly_series)
    inferred_target_period = max(last_target_period + 1, last_feature_month.asfreq("Q"))
    resolved_target_period = target_period or inferred_target_period
    if not isinstance(resolved_target_period, pd.Period):
        resolved_target_period = pd.Period(resolved_target_period, freq="Q")
    elif resolved_target_period.freqstr.startswith("Q") is False:
        resolved_target_period = resolved_target_period.asfreq("Q")

    target_end_month = resolved_target_period.asfreq("M", how="end")
    common_start = max(first_valid_periods)
    monthly_index = pd.period_range(common_start, target_end_month, freq="M")
    monthly = pd.concat(monthly_series, axis=1).reindex(monthly_index)

    # Remove columns that become too sparse after using the common sample start.
    usable_columns = [
        column
        for column in monthly.columns
        if monthly[column].notna().sum() >= minimum_months
        and monthly[column].dropna().std() > 0
    ]
    monthly = monthly[usable_columns]
    if len(usable_columns) < 3:
        raise ValueError(
            "Fewer than three monthly indicators remain after sample alignment."
        )

    quarterly_start = max(target_growth.index.min(), common_start.asfreq("Q"))
    quarterly_index = pd.period_range(
        quarterly_start, resolved_target_period, freq="Q"
    )
    quarterly = target_growth.reindex(quarterly_index).astype(float)
    quarterly.loc[resolved_target_period] = np.nan

    observed_quarters = int(
        quarterly.loc[quarterly.index < resolved_target_period].notna().sum()
    )
    if observed_quarters < minimum_quarters:
        raise ValueError(
            f"Only {observed_quarters} historical GDP quarters are available; "
            f"at least {minimum_quarters} are required for the Dynamic Factor Model."
        )

    resolved_data_as_of = data_as_of or observations["observation_date"].max()
    return MixedFrequencyDataset(
        target_name=target_series,
        target_period=resolved_target_period,
        monthly_features=monthly.astype(float),
        quarterly_target=quarterly,
        feature_names=list(monthly.columns),
        data_as_of=pd.Timestamp(resolved_data_as_of),
        last_available_periods=last_available_periods,
    )

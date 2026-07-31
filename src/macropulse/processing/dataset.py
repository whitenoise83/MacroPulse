from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from macropulse.config import SeriesDefinition
from macropulse.processing.transforms import transform_series


@dataclass
class BridgeDataset:
    target_name: str
    target_period: pd.Period
    training_frame: pd.DataFrame
    current_features: pd.DataFrame
    feature_names: list[str]
    imputed_features: list[str]
    data_as_of: pd.Timestamp


def build_bridge_dataset(
    observations: pd.DataFrame,
    definitions: list[SeriesDefinition],
    target_series: str,
    target_period: pd.Period | None = None,
    data_as_of: pd.Timestamp | None = None,
) -> BridgeDataset:
    if observations.empty:
        raise ValueError("No observations are available. Run the download script first.")

    observations = observations.copy()
    observations["observation_date"] = pd.to_datetime(
        observations["observation_date"]
    )
    observations = observations.sort_values(["series_id", "observation_date"])

    definition_map = {definition.series_id: definition for definition in definitions}
    if target_series not in definition_map:
        raise KeyError(f"Target series {target_series} is not in the registry.")

    target_definition = definition_map[target_series]
    target_raw = (
        observations.loc[observations["series_id"] == target_series]
        .set_index("observation_date")["value"]
        .sort_index()
    )
    target_growth = transform_series(target_raw, target_definition.transform)
    target_growth.index = target_growth.index.to_period("Q")
    target_growth = target_growth.groupby(level=0).last()
    target_growth.name = "target"

    feature_frames: list[pd.Series] = []
    for definition in definitions:
        if definition.role != "feature":
            continue

        raw = (
            observations.loc[observations["series_id"] == definition.series_id]
            .set_index("observation_date")["value"]
            .sort_index()
        )
        if raw.empty:
            continue

        transformed = transform_series(raw, definition.transform)
        quarterly = transformed.groupby(transformed.index.to_period("Q")).mean()
        quarterly.name = definition.series_id
        feature_frames.append(quarterly)

    if not feature_frames:
        raise ValueError("No usable feature series were found.")

    features = pd.concat(feature_frames, axis=1).sort_index()

    last_target_period = target_growth.dropna().index.max()
    last_feature_period = features.dropna(how="all").index.max()
    inferred_target_period = max(last_target_period + 1, last_feature_period)
    target_period = target_period or inferred_target_period
    if not isinstance(target_period, pd.Period):
        target_period = pd.Period(target_period, freq="Q")

    all_periods = pd.period_range(features.index.min(), target_period, freq="Q")
    features = features.reindex(all_periods)

    current = features.loc[[target_period]].copy()
    imputed_features: list[str] = []

    # Current-quarter data can be ragged. For Phase 1, a missing current feature
    # uses its most recently known quarterly value. This is a transparent
    # no-news assumption and is reported in the dashboard.
    for column in current.columns:
        if pd.isna(current.iloc[0][column]):
            previous = features.loc[:target_period, column].ffill().iloc[-1]
            current.loc[target_period, column] = previous
            imputed_features.append(column)

    combined = pd.concat([target_growth, features], axis=1)
    training = combined.loc[combined.index < target_period].dropna()

    if len(training) < 24:
        raise ValueError(
            f"Only {len(training)} complete quarterly observations are available; "
            "at least 24 are required."
        )

    resolved_data_as_of = data_as_of or observations["observation_date"].max()

    return BridgeDataset(
        target_name=target_series,
        target_period=target_period,
        training_frame=training,
        current_features=current,
        feature_names=list(features.columns),
        imputed_features=imputed_features,
        data_as_of=pd.Timestamp(resolved_data_as_of),
    )

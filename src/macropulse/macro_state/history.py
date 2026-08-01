from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any, Iterable

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.macro_state.engine import (
    GDP_TARGET,
    INFLATION_TARGETS,
    LABOUR_TARGETS,
    build_dimensions,
    classify_regime,
)
from macropulse.macro_state.versioning import load_macro_state_governance


@dataclass(frozen=True)
class HistoricalStateRow:
    state_date: date
    growth_score: float
    inflation_score: float
    labour_score: float
    growth_lower: float
    growth_upper: float
    inflation_lower: float
    inflation_upper: float
    labour_lower: float
    labour_upper: float
    growth_label: str
    inflation_label: str
    labour_label: str
    primary_regime: str
    primary_regime_label: str
    primary_regime_strength: float
    possible_regimes: tuple[str, ...]
    source_cutoff_spread_days: int
    no_look_ahead_pass: bool
    source_bundle_hash: str


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def month_end_dates(start: date, end: date) -> list[date]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if end_ts < start_ts:
        raise ValueError("History end date must be on or after start date.")
    dates = pd.date_range(
        start=start_ts,
        end=end_ts,
        freq="ME",
    )
    return [item.date() for item in dates]


def reconstruction_dates(start: date, end: date) -> list[date]:
    """Return month ends plus the explicitly requested terminal as-of date."""
    dates = month_end_dates(start, end)
    if start <= end and end not in dates:
        dates.append(end)
    return sorted(set(dates))


def _latest_rows_by_target(
    frame: pd.DataFrame,
    target_column: str,
    date_column: str,
    state_date: date,
    required_targets: Iterable[str],
) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    data = frame.copy()
    data[date_column] = pd.to_datetime(data[date_column]).dt.date
    data = data.loc[data[date_column] <= state_date].copy()
    if data.empty:
        return data
    data = data.sort_values(
        [target_column, date_column],
        ascending=[True, False],
    )
    data = data.drop_duplicates(subset=[target_column], keep="first")
    targets = set(data[target_column].astype(str))
    missing = sorted(set(required_targets).difference(targets))
    if missing:
        return pd.DataFrame(columns=data.columns)
    return data.loc[
        data[target_column].astype(str).isin(required_targets)
    ].copy()


def _gdp_history_candidates(
    repository: MacroRepository,
    state_date: date,
) -> pd.DataFrame:
    return repository.query_df(
        """
        SELECT
            run_id,
            model_id,
            model_version,
            information_cutoff,
            data_as_of,
            target_period,
            forecast_stage,
            production_forecast AS point_forecast,
            lower_80,
            upper_80,
            created_at
        FROM forecast_registry
        WHERE model_id = 'US_GDP_NOWCAST_1A'
          AND status = 'success'
          AND information_cutoff <= ?
        ORDER BY information_cutoff DESC, created_at DESC
        """,
        [state_date],
    )


def _live_history_candidates(
    repository: MacroRepository,
    state_date: date,
    run_table: str,
    forecast_table: str,
    model_id: str,
) -> pd.DataFrame:
    return repository.query_df(
        f"""
        SELECT
            r.run_id,
            r.model_id,
            r.model_version,
            r.information_cutoff,
            r.data_as_of,
            r.run_timestamp,
            f.target_series,
            f.target_name,
            f.target_period,
            f.forecast_stage,
            f.stable_point_forecast AS point_forecast,
            f.lower_80,
            f.upper_80
        FROM {run_table} r
        JOIN {forecast_table} f
          ON r.run_id = f.run_id
        WHERE r.model_id = ?
          AND r.status = 'success'
          AND r.information_cutoff <= ?
        ORDER BY r.information_cutoff DESC, r.run_timestamp DESC
        """,
        [model_id, state_date],
    )


def _select_latest_complete_live_run(
    candidates: pd.DataFrame,
    required_targets: tuple[str, ...],
) -> pd.DataFrame:
    if candidates.empty:
        return candidates
    for run_id in candidates["run_id"].drop_duplicates().tolist():
        run_rows = candidates.loc[candidates["run_id"] == run_id].copy()
        observed = set(run_rows["target_series"].astype(str))
        if set(required_targets).issubset(observed):
            return run_rows.loc[
                run_rows["target_series"].astype(str).isin(required_targets)
            ].copy()
    return pd.DataFrame(columns=candidates.columns)


def historical_source_bundle(
    repository: MacroRepository,
    state_date: date,
    config: dict[str, Any],
) -> pd.DataFrame:
    gdp_candidates = _gdp_history_candidates(repository, state_date)
    if gdp_candidates.empty:
        return pd.DataFrame()
    gdp = gdp_candidates.iloc[[0]].copy()
    gdp_input = pd.DataFrame(
        {
            "source_model_id": gdp["model_id"].astype(str),
            "source_model_version": gdp["model_version"].astype(str),
            "source_run_id": gdp["run_id"].astype(str),
            "source_target": GDP_TARGET,
            "source_target_name": "Real GDP growth",
            "target_period": gdp["target_period"].astype(str),
            "forecast_stage": gdp["forecast_stage"].astype(str),
            "point_forecast": pd.to_numeric(
                gdp["point_forecast"], errors="raise"
            ),
            "lower_80": pd.to_numeric(gdp["lower_80"], errors="raise"),
            "upper_80": pd.to_numeric(gdp["upper_80"], errors="raise"),
            "information_cutoff": pd.to_datetime(
                gdp["information_cutoff"]
            ).dt.date,
            "data_as_of": pd.to_datetime(
                gdp["data_as_of"]
            ).dt.date,
        }
    )

    inflation_candidates = _live_history_candidates(
        repository,
        state_date,
        "inflation_live_runs",
        "inflation_live_forecasts",
        "US_INFLATION_NOWCAST_1B",
    )
    inflation = _select_latest_complete_live_run(
        inflation_candidates,
        INFLATION_TARGETS,
    )
    if inflation.empty:
        return pd.DataFrame()
    inflation_input = pd.DataFrame(
        {
            "source_model_id": inflation["model_id"].astype(str),
            "source_model_version": inflation["model_version"].astype(str),
            "source_run_id": inflation["run_id"].astype(str),
            "source_target": inflation["target_series"].astype(str),
            "source_target_name": inflation["target_name"].astype(str),
            "target_period": inflation["target_period"].astype(str),
            "forecast_stage": inflation["forecast_stage"].astype(str),
            "point_forecast": pd.to_numeric(
                inflation["point_forecast"], errors="raise"
            ),
            "lower_80": pd.to_numeric(
                inflation["lower_80"], errors="raise"
            ),
            "upper_80": pd.to_numeric(
                inflation["upper_80"], errors="raise"
            ),
            "information_cutoff": pd.to_datetime(
                inflation["information_cutoff"]
            ).dt.date,
            "data_as_of": pd.to_datetime(
                inflation["data_as_of"]
            ).dt.date,
        }
    )

    labour_candidates = _live_history_candidates(
        repository,
        state_date,
        "labour_live_runs",
        "labour_live_forecasts",
        "US_LABOUR_NOWCAST_1C",
    )
    labour = _select_latest_complete_live_run(
        labour_candidates,
        LABOUR_TARGETS,
    )
    if labour.empty:
        return pd.DataFrame()
    labour_input = pd.DataFrame(
        {
            "source_model_id": labour["model_id"].astype(str),
            "source_model_version": labour["model_version"].astype(str),
            "source_run_id": labour["run_id"].astype(str),
            "source_target": labour["target_series"].astype(str),
            "source_target_name": labour["target_name"].astype(str),
            "target_period": labour["target_period"].astype(str),
            "forecast_stage": labour["forecast_stage"].astype(str),
            "point_forecast": pd.to_numeric(
                labour["point_forecast"], errors="raise"
            ),
            "lower_80": pd.to_numeric(
                labour["lower_80"], errors="raise"
            ),
            "upper_80": pd.to_numeric(
                labour["upper_80"], errors="raise"
            ),
            "information_cutoff": pd.to_datetime(
                labour["information_cutoff"]
            ).dt.date,
            "data_as_of": pd.to_datetime(
                labour["data_as_of"]
            ).dt.date,
        }
    )

    inputs = pd.concat(
        [gdp_input, inflation_input, labour_input],
        ignore_index=True,
    )

    max_ages = config["history"]["maximum_source_age_days"]
    model_to_key = {
        "US_GDP_NOWCAST_1A": "GDP",
        "US_INFLATION_NOWCAST_1B": "inflation",
        "US_LABOUR_NOWCAST_1C": "labour",
    }
    for model_id, rows in inputs.groupby("source_model_id"):
        source_key = model_to_key[str(model_id)]
        newest_cutoff = max(rows["information_cutoff"])
        age = (state_date - newest_cutoff).days
        if age > int(max_ages[source_key]):
            return pd.DataFrame()

    inputs["source_hash"] = [
        _hash(
            {
                "source_model_id": row.source_model_id,
                "source_model_version": row.source_model_version,
                "source_run_id": row.source_run_id,
                "source_target": row.source_target,
                "target_period": row.target_period,
                "forecast_stage": row.forecast_stage,
                "point_forecast": row.point_forecast,
                "lower_80": row.lower_80,
                "upper_80": row.upper_80,
                "information_cutoff": row.information_cutoff,
                "data_as_of": row.data_as_of,
            }
        )
        for row in inputs.itertuples(index=False)
    ]
    return inputs


def possible_regimes_from_intervals(
    growth_lower: float,
    growth_upper: float,
    inflation_lower: float,
    inflation_upper: float,
    labour_lower: float,
    labour_upper: float,
) -> tuple[str, ...]:
    axes = [
        np.linspace(growth_lower, growth_upper, 9),
        np.linspace(inflation_lower, inflation_upper, 9),
        np.linspace(labour_lower, labour_upper, 9),
    ]
    regimes = {
        classify_regime(g, i, l)[0]
        for g, i, l in product(*axes)
    }
    return tuple(sorted(regimes))


def reconstruct_history(
    repository: MacroRepository,
    start_date: date,
    end_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = load_macro_state_governance()
    state_rows: list[dict[str, Any]] = []
    input_rows: list[pd.DataFrame] = []

    for state_date in reconstruction_dates(start_date, end_date):
        inputs = historical_source_bundle(repository, state_date, config)
        if inputs.empty:
            continue

        dimensions = build_dimensions(inputs, config)
        scores = {item.dimension: item for item in dimensions}
        regime = classify_regime(
            scores["growth"].score,
            scores["inflation"].score,
            scores["labour"].score,
        )
        possible = possible_regimes_from_intervals(
            scores["growth"].lower_score,
            scores["growth"].upper_score,
            scores["inflation"].lower_score,
            scores["inflation"].upper_score,
            scores["labour"].lower_score,
            scores["labour"].upper_score,
        )

        oldest = min(inputs["information_cutoff"])
        newest = max(inputs["information_cutoff"])
        spread = int((newest - oldest).days)
        no_look_ahead = bool(
            all(
                pd.Timestamp(item).date() <= state_date
                for item in inputs["information_cutoff"]
            )
        )
        bundle_payload = inputs[
            [
                "source_model_id",
                "source_model_version",
                "source_run_id",
                "source_target",
                "target_period",
                "forecast_stage",
                "point_forecast",
                "lower_80",
                "upper_80",
                "information_cutoff",
                "data_as_of",
                "source_hash",
            ]
        ].to_dict(orient="records")
        source_bundle_hash = _hash(bundle_payload)

        state_rows.append(
            {
                "state_date": state_date,
                "growth_score": scores["growth"].score,
                "inflation_score": scores["inflation"].score,
                "labour_score": scores["labour"].score,
                "growth_lower": scores["growth"].lower_score,
                "growth_upper": scores["growth"].upper_score,
                "inflation_lower": scores["inflation"].lower_score,
                "inflation_upper": scores["inflation"].upper_score,
                "labour_lower": scores["labour"].lower_score,
                "labour_upper": scores["labour"].upper_score,
                "growth_label": scores["growth"].label,
                "inflation_label": scores["inflation"].label,
                "labour_label": scores["labour"].label,
                "primary_regime": regime[0],
                "primary_regime_label": regime[1],
                "primary_regime_strength": regime[2],
                "possible_regimes_json": json.dumps(possible),
                "possible_regime_count": len(possible),
                "source_cutoff_spread_days": spread,
                "no_look_ahead_pass": no_look_ahead,
                "source_bundle_hash": source_bundle_hash,
            }
        )
        month_inputs = inputs.copy()
        month_inputs.insert(0, "state_date", state_date)
        input_rows.append(month_inputs)

    states = pd.DataFrame(state_rows)
    all_inputs = (
        pd.concat(input_rows, ignore_index=True)
        if input_rows
        else pd.DataFrame()
    )
    return states, all_inputs


def transition_matrix(states: pd.DataFrame) -> pd.DataFrame:
    if states.empty or len(states) < 2:
        return pd.DataFrame()
    ordered = states.sort_values("state_date").copy()
    ordered["_month_ordinal"] = pd.PeriodIndex(
        ordered["state_date"], freq="M"
    ).asi8
    ordered["next_regime"] = ordered["primary_regime"].shift(-1)
    ordered["next_month_ordinal"] = ordered["_month_ordinal"].shift(-1)
    transitions = ordered.loc[
        ordered["next_regime"].notna()
        & (
            ordered["next_month_ordinal"]
            - ordered["_month_ordinal"]
            == 1
        )
    ].copy()
    if transitions.empty:
        return pd.DataFrame()
    return pd.crosstab(
        transitions["primary_regime"],
        transitions["next_regime"],
        normalize="index",
    )


def regime_durations(states: pd.DataFrame) -> pd.DataFrame:
    if states.empty:
        return pd.DataFrame()
    ordered = states.sort_values("state_date").copy()
    ordered["_month_ordinal"] = pd.PeriodIndex(
        ordered["state_date"], freq="M"
    ).asi8
    gap = ordered["_month_ordinal"].diff().fillna(1).ne(1)
    regime_change = (
        ordered["primary_regime"]
        != ordered["primary_regime"].shift()
    )
    ordered["segment"] = (gap | regime_change).cumsum()
    return (
        ordered.groupby(
            ["segment", "primary_regime", "primary_regime_label"],
            as_index=False,
        )
        .agg(
            start_date=("state_date", "min"),
            end_date=("state_date", "max"),
            months=("state_date", "size"),
        )
        .drop(columns=["segment"])
    )

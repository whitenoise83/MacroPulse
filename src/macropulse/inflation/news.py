from __future__ import annotations

import json
import uuid
from typing import Any

import numpy as np
import pandas as pd

from macropulse.data.repository import MacroRepository
from macropulse.inflation.live import estimate_target_models


KEYS = ["series_id", "observation_date"]


def _normalise_information_set(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["observation_date"] = pd.to_datetime(output["observation_date"])
    output["value"] = pd.to_numeric(output["value"], errors="coerce")
    output = output.dropna(subset=["series_id", "observation_date", "value"])
    output = output.sort_values(KEYS).drop_duplicates(KEYS, keep="last")
    return output.reset_index(drop=True)


def _forecast(
    observations: pd.DataFrame,
    target_series: str,
    target_period: str,
    model_name: str,
) -> float:
    _, models = estimate_target_models(
        observations,
        target_series,
        target_period=pd.Period(target_period, freq="M"),
    )
    if model_name not in models:
        raise RuntimeError(f"Model {model_name} is unavailable for news decomposition.")
    return float(models[model_name].point_forecast)


def _change_records(previous: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    left = previous[KEYS + ["value"]].rename(columns={"value": "previous_value"})
    right = current[KEYS + ["value"]].rename(columns={"value": "current_value"})
    merged = left.merge(right, on=KEYS, how="outer", indicator=True)
    revised = merged.loc[
        (merged["_merge"] == "both")
        & (~np.isclose(
            pd.to_numeric(merged["previous_value"], errors="coerce"),
            pd.to_numeric(merged["current_value"], errors="coerce"),
            rtol=0.0,
            atol=1e-12,
            equal_nan=True,
        ))
    ].copy()
    revised["change_type"] = "revision"
    added = merged.loc[merged["_merge"] == "right_only"].copy()
    added["change_type"] = "new_observation"
    removed = merged.loc[merged["_merge"] == "left_only"].copy()
    removed["change_type"] = "removed_observation"
    changes = pd.concat([revised, added, removed], ignore_index=True)
    if changes.empty:
        return pd.DataFrame(
            columns=KEYS + ["change_type", "previous_value", "current_value", "value_change"]
        )
    changes["value_change"] = (
        pd.to_numeric(changes["current_value"], errors="coerce").fillna(0.0)
        - pd.to_numeric(changes["previous_value"], errors="coerce").fillna(0.0)
    )
    return changes[
        KEYS + ["change_type", "previous_value", "current_value", "value_change"]
    ].sort_values(["change_type", "series_id", "observation_date"])


def _apply_series_change(
    working: pd.DataFrame,
    current: pd.DataFrame,
    series_id: str,
    change_type: str,
) -> pd.DataFrame:
    output = working.copy()
    current_series = current.loc[current["series_id"] == series_id].copy()
    if change_type == "revision":
        current_map = current_series.set_index("observation_date")["value"]
        mask = (output["series_id"] == series_id) & output["observation_date"].isin(current_map.index)
        output.loc[mask, "value"] = output.loc[mask, "observation_date"].map(current_map)
    elif change_type == "removed_observation":
        current_dates = set(current_series["observation_date"])
        mask = (output["series_id"] == series_id) & (~output["observation_date"].isin(current_dates))
        output = output.loc[~mask].copy()
    elif change_type == "new_observation":
        existing = set(
            zip(output["series_id"].astype(str), output["observation_date"])
        )
        additions = current_series.loc[
            [
                (str(row.series_id), row.observation_date) not in existing
                for row in current_series.itertuples(index=False)
            ]
        ]
        output = pd.concat([output, additions], ignore_index=True, sort=False)
    else:
        raise ValueError(f"Unknown change type: {change_type}")
    return _normalise_information_set(output)


def _decompose_target(
    previous_info: pd.DataFrame,
    current_info: pd.DataFrame,
    previous_forecast: pd.Series,
    current_forecast: pd.Series,
    decomposition_id: str,
    timestamp: pd.Timestamp,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    target_series = str(current_forecast["target_series"])
    target_period = str(current_forecast["target_period"])
    previous_model = str(previous_forecast["stable_model_name"])
    current_model = str(current_forecast["stable_model_name"])
    previous_saved = float(previous_forecast["stable_point_forecast"])
    current_saved = float(current_forecast["stable_point_forecast"])
    changes = _change_records(previous_info, current_info)

    contributions: list[dict[str, Any]] = []
    release_changes: list[dict[str, Any]] = []
    for row in changes.itertuples(index=False):
        release_changes.append(
            {
                "decomposition_id": decomposition_id,
                "target_series": target_series,
                "series_id": str(row.series_id),
                "observation_date": pd.Timestamp(row.observation_date).date(),
                "change_type": str(row.change_type),
                "previous_value": row.previous_value,
                "current_value": row.current_value,
                "value_change": row.value_change,
                "created_at": timestamp,
            }
        )

    previous_refit = _forecast(previous_info, target_series, target_period, previous_model)
    model_refit_impact = previous_refit - previous_saved
    working = previous_info.copy()
    running_forecast = previous_refit
    revision_impact = 0.0
    new_data_impact = 0.0

    for change_type, bucket in [
        ("revision", "revision"),
        ("removed_observation", "revision"),
        ("new_observation", "new_data"),
    ]:
        series_ids = sorted(
            changes.loc[changes["change_type"] == change_type, "series_id"].astype(str).unique()
        )
        for series_id in series_ids:
            before = running_forecast
            working = _apply_series_change(working, current_info, series_id, change_type)
            running_forecast = _forecast(working, target_series, target_period, previous_model)
            impact = running_forecast - before
            if bucket == "revision":
                revision_impact += impact
            else:
                new_data_impact += impact
            detail_rows = changes.loc[
                (changes["change_type"] == change_type)
                & (changes["series_id"].astype(str) == series_id)
            ]
            contributions.append(
                {
                    "decomposition_id": decomposition_id,
                    "target_series": target_series,
                    "contribution_type": bucket,
                    "model_name": previous_model,
                    "series_id": series_id,
                    "impact": float(impact),
                    "details_json": json.dumps(
                        detail_rows.where(pd.notna(detail_rows), None).to_dict("records"),
                        default=str,
                        sort_keys=True,
                    ),
                    "created_at": timestamp,
                }
            )

    previous_model_on_current = running_forecast
    current_refit = _forecast(current_info, target_series, target_period, current_model)
    policy_change_impact = current_refit - previous_model_on_current
    residual = (
        current_saved
        - previous_saved
        - model_refit_impact
        - revision_impact
        - new_data_impact
        - policy_change_impact
    )
    total_change = current_saved - previous_saved
    run = {
        "decomposition_id": decomposition_id,
        "current_run_id": str(current_forecast["run_id"]),
        "previous_run_id": str(previous_forecast["run_id"]),
        "target_series": target_series,
        "target_period": target_period,
        "status": "success",
        "previous_forecast": previous_saved,
        "current_forecast": current_saved,
        "total_change": total_change,
        "new_data_impact": new_data_impact,
        "revision_impact": revision_impact,
        "model_refit_impact": model_refit_impact,
        "policy_change_impact": policy_change_impact,
        "residual_interaction": residual,
        "details_json": json.dumps(
            {
                "previous_model": previous_model,
                "current_model": current_model,
                "changed_observations": int(len(changes)),
                "new_observations": int((changes["change_type"] == "new_observation").sum()),
                "revisions": int((changes["change_type"] == "revision").sum()),
                "removed_observations": int((changes["change_type"] == "removed_observation").sum()),
                "attribution_order": ["revision", "removed_observation", "new_observation", "policy_change"],
            },
            sort_keys=True,
        ),
        "created_at": timestamp,
    }
    return run, contributions, release_changes


def build_inflation_news_decomposition(
    repository: MacroRepository,
    current_run_id: str,
) -> dict[str, Any]:
    current_run = repository.query_df(
        "SELECT * FROM inflation_live_runs WHERE run_id = ?", [current_run_id]
    )
    if current_run.empty:
        raise RuntimeError(f"Governed inflation run {current_run_id} does not exist.")
    current_timestamp = current_run.iloc[0]["run_timestamp"]
    previous = repository.query_df(
        """
        SELECT run_id
        FROM inflation_live_runs
        WHERE status = 'success' AND run_timestamp < ?
        ORDER BY run_timestamp DESC
        LIMIT 1
        """,
        [current_timestamp],
    )
    current_forecasts = repository.query_df(
        "SELECT * FROM inflation_live_forecasts WHERE run_id = ? ORDER BY target_series",
        [current_run_id],
    )
    timestamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    run_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    change_rows: list[dict[str, Any]] = []

    if previous.empty:
        for row in current_forecasts.itertuples(index=False):
            run_rows.append(
                {
                    "decomposition_id": str(uuid.uuid4()),
                    "current_run_id": current_run_id,
                    "previous_run_id": None,
                    "target_series": str(row.target_series),
                    "target_period": str(row.target_period),
                    "status": "no_previous_run",
                    "previous_forecast": np.nan,
                    "current_forecast": float(row.stable_point_forecast),
                    "total_change": np.nan,
                    "new_data_impact": np.nan,
                    "revision_impact": np.nan,
                    "model_refit_impact": np.nan,
                    "policy_change_impact": np.nan,
                    "residual_interaction": np.nan,
                    "details_json": json.dumps({"reason": "first governed live run"}),
                    "created_at": timestamp,
                }
            )
        repository.save_inflation_news_outputs(
            pd.DataFrame(run_rows), pd.DataFrame(), pd.DataFrame()
        )
        return {"status": "no_previous_run", "targets": len(run_rows)}

    previous_run_id = str(previous.iloc[0]["run_id"])
    previous_forecasts = repository.query_df(
        "SELECT * FROM inflation_live_forecasts WHERE run_id = ? ORDER BY target_series",
        [previous_run_id],
    )
    previous_info = _normalise_information_set(
        repository.inflation_live_information_set(previous_run_id)
    )
    current_info = _normalise_information_set(
        repository.inflation_live_information_set(current_run_id)
    )

    for _, current_row in current_forecasts.iterrows():
        target = str(current_row["target_series"])
        matching = previous_forecasts.loc[
            (previous_forecasts["target_series"] == target)
            & (previous_forecasts["target_period"].astype(str) == str(current_row["target_period"]))
        ]
        decomposition_id = str(uuid.uuid4())
        if matching.empty:
            previous_target = previous_forecasts.loc[
                previous_forecasts["target_series"] == target
            ]
            run_rows.append(
                {
                    "decomposition_id": decomposition_id,
                    "current_run_id": current_run_id,
                    "previous_run_id": previous_run_id,
                    "target_series": target,
                    "target_period": str(current_row["target_period"]),
                    "status": "target_roll",
                    "previous_forecast": (
                        float(previous_target.iloc[0]["stable_point_forecast"])
                        if not previous_target.empty else np.nan
                    ),
                    "current_forecast": float(current_row["stable_point_forecast"]),
                    "total_change": np.nan,
                    "new_data_impact": np.nan,
                    "revision_impact": np.nan,
                    "model_refit_impact": np.nan,
                    "policy_change_impact": np.nan,
                    "residual_interaction": np.nan,
                    "details_json": json.dumps(
                        {
                            "reason": "target month changed between governed runs",
                            "previous_target_period": (
                                str(previous_target.iloc[0]["target_period"])
                                if not previous_target.empty else None
                            ),
                        },
                        sort_keys=True,
                    ),
                    "created_at": timestamp,
                }
            )
            continue
        previous_row = matching.iloc[0]
        run, contributions, changes = _decompose_target(
            previous_info,
            current_info,
            previous_row,
            current_row,
            decomposition_id,
            timestamp,
        )
        run_rows.append(run)
        contribution_rows.extend(contributions)
        change_rows.extend(changes)

    repository.save_inflation_news_outputs(
        pd.DataFrame(run_rows),
        pd.DataFrame(contribution_rows),
        pd.DataFrame(change_rows),
    )
    successful = [row for row in run_rows if row["status"] == "success"]
    maximum_residual = max(
        (abs(float(row["residual_interaction"])) for row in successful),
        default=0.0,
    )
    return {
        "status": "success",
        "previous_run_id": previous_run_id,
        "targets": len(run_rows),
        "comparable_targets": len(successful),
        "maximum_residual": maximum_residual,
    }

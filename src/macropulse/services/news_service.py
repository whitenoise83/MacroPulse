from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from macropulse.config import SeriesDefinition
from macropulse.data.repository import MacroRepository
from macropulse.models.baseline import BridgeFit, estimate_bridge_ridge
from macropulse.models.dynamic_factor import DynamicFactorFit, estimate_dynamic_factor
from macropulse.processing.dataset import build_bridge_dataset
from macropulse.processing.mixed_frequency import build_mixed_frequency_dataset


PRODUCTION_COMPONENTS = ("Bridge Ridge", "Dynamic Factor Model")


def _normalise_weights(weights: dict[str, float] | None) -> dict[str, float]:
    values = {
        name: float((weights or {}).get(name, 0.0))
        for name in PRODUCTION_COMPONENTS
    }
    total = sum(max(value, 0.0) for value in values.values())
    if total <= 0:
        return {"Bridge Ridge": 1.0, "Dynamic Factor Model": 0.0}
    return {name: max(value, 0.0) / total for name, value in values.items()}


def _metrics_weights(metrics_json: str | None) -> dict[str, float]:
    if not metrics_json:
        return _normalise_weights(None)
    try:
        metrics = json.loads(metrics_json)
    except (TypeError, json.JSONDecodeError):
        return _normalise_weights(None)
    return _normalise_weights(metrics.get("production_weights"))


def _forecast_map(repository: MacroRepository, run_id: str) -> dict[str, float]:
    frame = repository.query_df(
        """
        SELECT model_name, point_forecast
        FROM forecasts
        WHERE run_id = ?
        """,
        [run_id],
    )
    return {
        str(row.model_name): float(row.point_forecast)
        for row in frame.itertuples(index=False)
        if pd.notna(row.point_forecast)
    }



def _mappings_close(
    left: dict[str, float],
    right: dict[str, float],
    tolerance: float = 1e-10,
) -> bool:
    keys = set(left) | set(right)
    return all(
        abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) <= tolerance
        for key in keys
    )


def _is_no_change_comparison(
    release_changes: pd.DataFrame,
    previous_weights: dict[str, float],
    current_weights: dict[str, float],
    previous_components: dict[str, float],
    current_components: dict[str, float],
    total_change: float,
    tolerance: float = 1e-10,
) -> bool:
    return (
        release_changes.empty
        and abs(float(total_change)) <= tolerance
        and _mappings_close(previous_weights, current_weights, tolerance)
        and _mappings_close(previous_components, current_components, tolerance)
    )


def _weight_change_impact(
    previous_weights: dict[str, float],
    current_weights: dict[str, float],
    current_components: dict[str, float],
) -> float:
    return float(
        sum(
            (float(current_weights.get(name, 0.0)) - float(previous_weights.get(name, 0.0)))
            * float(current_components.get(name, 0.0))
            for name in PRODUCTION_COMPONENTS
        )
    )


def _is_weight_only_comparison(
    release_changes: pd.DataFrame,
    previous_weights: dict[str, float],
    current_weights: dict[str, float],
    previous_components: dict[str, float],
    current_components: dict[str, float],
    total_change: float,
    tolerance: float = 1e-10,
) -> bool:
    if not release_changes.empty:
        return False
    if not _mappings_close(previous_components, current_components, tolerance):
        return False
    if _mappings_close(previous_weights, current_weights, tolerance):
        return False
    expected = _weight_change_impact(
        previous_weights,
        current_weights,
        current_components,
    )
    return abs(float(total_change) - expected) <= tolerance


def _save_no_change_result(
    repository: MacroRepository,
    decomposition_id: str,
    current_run_id: str,
    previous_run_id: str,
    target_period: pd.Period,
    previous_forecast: float,
    current_forecast: float,
    details: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    details = {
        **details,
        "decomposition_kind": "no_change",
        "dfm_update_count": 0,
        "dfm_revision_count": 0,
        "reconciliation_error": 0.0,
        "message": "No raw observations, component forecasts, or production weights changed.",
    }
    news_run = pd.DataFrame(
        [
            {
                "decomposition_id": decomposition_id,
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "target_period": str(target_period),
                "status": "success",
                "previous_forecast": previous_forecast,
                "current_forecast": current_forecast,
                "total_change": 0.0,
                "bridge_data_impact": 0.0,
                "bridge_refit_impact": 0.0,
                "dfm_news_impact": 0.0,
                "dfm_revision_impact": 0.0,
                "dfm_refit_impact": 0.0,
                "weight_change_impact": 0.0,
                "residual_interaction": 0.0,
                "details_json": json.dumps(details),
                "created_at": created_at,
            }
        ]
    )
    repository.save_news_outputs(news_run, pd.DataFrame(), pd.DataFrame())
    return {
        "decomposition_id": decomposition_id,
        "status": "success",
        "previous_forecast": previous_forecast,
        "current_forecast": current_forecast,
        "total_change": 0.0,
        "contributions": pd.DataFrame(),
        "release_changes": pd.DataFrame(),
        "details": details,
    }


def _save_weight_only_result(
    repository: MacroRepository,
    decomposition_id: str,
    current_run_id: str,
    previous_run_id: str,
    target_period: pd.Period,
    previous_forecast: float,
    current_forecast: float,
    weight_change_impact: float,
    details: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    details = {
        **details,
        "decomposition_kind": "weight_only",
        "dfm_update_count": 0,
        "dfm_revision_count": 0,
        "reconciliation_error": 0.0,
        "message": (
            "No raw observations or component forecasts changed. "
            "The production forecast changed only because the selected model or "
            "ensemble weights changed."
        ),
    }
    news_run = pd.DataFrame(
        [
            {
                "decomposition_id": decomposition_id,
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "target_period": str(target_period),
                "status": "success",
                "previous_forecast": previous_forecast,
                "current_forecast": current_forecast,
                "total_change": float(weight_change_impact),
                "bridge_data_impact": 0.0,
                "bridge_refit_impact": 0.0,
                "dfm_news_impact": 0.0,
                "dfm_revision_impact": 0.0,
                "dfm_refit_impact": 0.0,
                "weight_change_impact": float(weight_change_impact),
                "residual_interaction": 0.0,
                "details_json": json.dumps(details),
                "created_at": created_at,
            }
        ]
    )
    contributions = _aggregate_contribution(
        "weight_change",
        "Production Ensemble",
        float(weight_change_impact),
        created_at,
    )
    if not contributions.empty:
        contributions.insert(0, "decomposition_id", decomposition_id)
    repository.save_news_outputs(news_run, contributions, pd.DataFrame())
    return {
        "decomposition_id": decomposition_id,
        "status": "success",
        "previous_forecast": previous_forecast,
        "current_forecast": current_forecast,
        "total_change": float(weight_change_impact),
        "contributions": contributions,
        "release_changes": pd.DataFrame(),
        "details": details,
    }


def compare_information_sets(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    tolerance: float = 1e-10,
) -> pd.DataFrame:
    columns = [
        "series_id",
        "observation_date",
        "change_type",
        "previous_value",
        "current_value",
        "value_change",
    ]
    if previous.empty and current.empty:
        return pd.DataFrame(columns=columns)

    def compact(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["series_id", "observation_date", value_name])
        out = frame.copy()
        out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date
        return (
            out.sort_values(["series_id", "observation_date", "retrieved_at"])
            .drop_duplicates(["series_id", "observation_date"], keep="last")
            [["series_id", "observation_date", "value"]]
            .rename(columns={"value": value_name})
        )

    left = compact(previous, "previous_value")
    right = compact(current, "current_value")
    merged = left.merge(right, on=["series_id", "observation_date"], how="outer")
    merged["value_change"] = merged["current_value"] - merged["previous_value"]
    merged["change_type"] = "unchanged"
    merged.loc[merged["previous_value"].isna() & merged["current_value"].notna(), "change_type"] = "new"
    merged.loc[merged["previous_value"].notna() & merged["current_value"].isna(), "change_type"] = "removed"
    revision_mask = (
        merged["previous_value"].notna()
        & merged["current_value"].notna()
        & (merged["value_change"].abs() > tolerance)
    )
    merged.loc[revision_mask, "change_type"] = "revision"
    return merged.loc[merged["change_type"] != "unchanged", columns].sort_values(
        ["series_id", "observation_date"]
    )


def _target_value(frame: pd.DataFrame, target_name: str) -> float:
    if frame is None or frame.empty:
        return 0.0
    if target_name in frame.columns:
        values = frame[target_name].dropna()
        return float(values.iloc[-1]) if not values.empty else 0.0
    return 0.0


def _details_frame(
    details: pd.DataFrame,
    contribution_type: str,
    model_weight: float,
    created_at: datetime,
) -> pd.DataFrame:
    columns = [
        "contribution_type",
        "model_name",
        "series_id",
        "observation_date",
        "previous_value",
        "current_value",
        "news",
        "weight",
        "impact",
        "created_at",
    ]
    if details is None or details.empty:
        return pd.DataFrame(columns=columns)

    frame = details.reset_index()
    is_revision = contribution_type == "dfm_revision"
    date_column = "revision date" if is_revision else "update date"
    series_column = "revised variable" if is_revision else "updated variable"
    previous_column = "observed (prev)" if is_revision else "forecast (prev)"
    current_column = "revised" if is_revision else "observed"
    news_column = "revision" if is_revision else "news"

    required = [date_column, series_column, "impact"]
    if any(column not in frame.columns for column in required):
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame(
        {
            "contribution_type": contribution_type,
            "model_name": "Dynamic Factor Model",
            "series_id": frame[series_column].astype(str),
            "observation_date": pd.to_datetime(frame[date_column], errors="coerce").dt.date,
            "previous_value": pd.to_numeric(frame.get(previous_column), errors="coerce"),
            "current_value": pd.to_numeric(frame.get(current_column), errors="coerce"),
            "news": pd.to_numeric(frame.get(news_column), errors="coerce"),
            "weight": pd.to_numeric(frame.get("weight"), errors="coerce") * model_weight,
            "impact": pd.to_numeric(frame["impact"], errors="coerce") * model_weight,
            "created_at": created_at,
        }
    )
    return out.loc[out["impact"].notna(), columns]


def _aggregate_contribution(
    contribution_type: str,
    model_name: str,
    impact: float,
    created_at: datetime,
) -> pd.DataFrame:
    if not np.isfinite(impact) or abs(float(impact)) < 1e-12:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "contribution_type": contribution_type,
                "model_name": model_name,
                "series_id": None,
                "observation_date": pd.NaT,
                "previous_value": np.nan,
                "current_value": np.nan,
                "news": np.nan,
                "weight": np.nan,
                "impact": float(impact),
                "created_at": created_at,
            }
        ]
    )


def build_news_decomposition(
    repository: MacroRepository,
    previous_run: pd.Series,
    current_run_id: str,
    current_observations: pd.DataFrame,
    current_bridge_fit: BridgeFit,
    current_dfm_fit: DynamicFactorFit | None,
    current_weights: dict[str, float],
    definitions: list[SeriesDefinition],
    target_series: str,
    target_period: pd.Period,
    ridge_alpha: float,
    interval: float,
    dfm_config: dict[str, Any],
) -> dict[str, Any]:
    created_at = datetime.now(UTC).replace(tzinfo=None)
    decomposition_id = str(uuid.uuid4())
    previous_run_id = str(previous_run["run_id"])
    previous_observations = repository.load_information_set(previous_run_id)
    release_changes = compare_information_sets(previous_observations, current_observations)

    base_details: dict[str, Any] = {
        "previous_run_id": previous_run_id,
        "current_run_id": current_run_id,
        "target_period": str(target_period),
        "raw_change_counts": release_changes["change_type"].value_counts().to_dict()
        if not release_changes.empty
        else {},
    }

    if previous_observations.empty:
        return _empty_news_result(
            repository,
            decomposition_id,
            current_run_id,
            previous_run_id,
            target_period,
            "no_previous_information_set",
            pd.DataFrame(columns=release_changes.columns),
            base_details,
            created_at,
        )

    previous_forecasts = _forecast_map(repository, previous_run_id)
    current_forecasts = _forecast_map(repository, current_run_id)
    required = ["Bridge Ridge", "Dynamic Factor Model"]
    if any(name not in previous_forecasts for name in required):
        return _empty_news_result(
            repository,
            decomposition_id,
            current_run_id,
            previous_run_id,
            target_period,
            "previous_components_unavailable",
            release_changes,
            base_details,
            created_at,
        )
    if current_dfm_fit is None or any(name not in current_forecasts for name in required):
        return _empty_news_result(
            repository,
            decomposition_id,
            current_run_id,
            previous_run_id,
            target_period,
            "current_dfm_unavailable",
            release_changes,
            base_details,
            created_at,
        )

    previous_weights = _metrics_weights(previous_run.get("metrics_json"))
    current_weights = _normalise_weights(current_weights)
    b0 = previous_forecasts["Bridge Ridge"]
    d0 = previous_forecasts["Dynamic Factor Model"]
    b1 = current_forecasts["Bridge Ridge"]
    d1 = current_forecasts["Dynamic Factor Model"]
    previous_production = previous_weights["Bridge Ridge"] * b0 + previous_weights["Dynamic Factor Model"] * d0
    current_production = current_weights["Bridge Ridge"] * b1 + current_weights["Dynamic Factor Model"] * d1
    total_change = current_production - previous_production

    previous_components = {"Bridge Ridge": b0, "Dynamic Factor Model": d0}
    current_components = {"Bridge Ridge": b1, "Dynamic Factor Model": d1}
    if _is_no_change_comparison(
        release_changes=release_changes,
        previous_weights=previous_weights,
        current_weights=current_weights,
        previous_components=previous_components,
        current_components=current_components,
        total_change=total_change,
    ):
        return _save_no_change_result(
            repository=repository,
            decomposition_id=decomposition_id,
            current_run_id=current_run_id,
            previous_run_id=previous_run_id,
            target_period=target_period,
            previous_forecast=previous_production,
            current_forecast=current_production,
            details={
                **base_details,
                "previous_weights": previous_weights,
                "current_weights": current_weights,
                "previous_components": previous_components,
                "current_components": current_components,
                "bridge_fixed_current": b0,
                "dfm_fixed_parameter_updated_forecast": d0,
            },
            created_at=created_at,
        )

    if _is_weight_only_comparison(
        release_changes=release_changes,
        previous_weights=previous_weights,
        current_weights=current_weights,
        previous_components=previous_components,
        current_components=current_components,
        total_change=total_change,
    ):
        weight_only_impact = _weight_change_impact(
            previous_weights,
            current_weights,
            current_components,
        )
        return _save_weight_only_result(
            repository=repository,
            decomposition_id=decomposition_id,
            current_run_id=current_run_id,
            previous_run_id=previous_run_id,
            target_period=target_period,
            previous_forecast=previous_production,
            current_forecast=current_production,
            weight_change_impact=weight_only_impact,
            details={
                **base_details,
                "previous_weights": previous_weights,
                "current_weights": current_weights,
                "previous_components": previous_components,
                "current_components": current_components,
                "bridge_fixed_current": b0,
                "dfm_fixed_parameter_updated_forecast": d0,
            },
            created_at=created_at,
        )

    previous_bridge_dataset = build_bridge_dataset(
        previous_observations,
        definitions,
        target_series,
        target_period=target_period,
        data_as_of=pd.to_datetime(previous_run["data_as_of"]),
    )
    previous_bridge_fit = estimate_bridge_ridge(
        previous_bridge_dataset.training_frame,
        previous_bridge_dataset.current_features,
        alpha=ridge_alpha,
        interval=interval,
    )
    bridge_fixed_current = previous_bridge_fit.predict_features(
        current_bridge_fit.current_features
    )
    bridge_feature_impacts = previous_bridge_fit.feature_contributions(
        previous_bridge_dataset.current_features,
        current_bridge_fit.current_features,
    )
    previous_bridge_weight = previous_weights["Bridge Ridge"]
    bridge_data_impact = float(bridge_fixed_current - b0) * previous_bridge_weight
    bridge_refit_impact = float(b1 - bridge_fixed_current) * previous_bridge_weight

    bridge_rows = pd.DataFrame(
        {
            "contribution_type": "bridge_feature_update",
            "model_name": "Bridge Ridge",
            "series_id": bridge_feature_impacts.index.astype(str),
            "observation_date": target_period.end_time.date(),
            "previous_value": [
                float(previous_bridge_dataset.current_features.iloc[0][name])
                for name in bridge_feature_impacts.index
            ],
            "current_value": [
                float(current_bridge_fit.current_features.iloc[0][name])
                for name in bridge_feature_impacts.index
            ],
            "news": [
                float(current_bridge_fit.current_features.iloc[0][name] - previous_bridge_dataset.current_features.iloc[0][name])
                for name in bridge_feature_impacts.index
            ],
            "weight": previous_bridge_weight,
            "impact": bridge_feature_impacts.values * previous_bridge_weight,
            "created_at": created_at,
        }
    )

    previous_mixed = build_mixed_frequency_dataset(
        previous_observations,
        definitions,
        target_series,
        target_period=target_period,
        data_as_of=pd.to_datetime(previous_run["data_as_of"]),
    )
    previous_dfm_fit = estimate_dynamic_factor(
        previous_mixed,
        interval=interval,
        factors=int(dfm_config.get("factors", 1)),
        factor_orders=int(dfm_config.get("factor_orders", 1)),
        idiosyncratic_ar1=bool(dfm_config.get("idiosyncratic_ar1", True)),
        maxiter=int(dfm_config.get("maxiter", 100)),
        tolerance=float(dfm_config.get("tolerance", 1e-4)),
        require_convergence=bool(dfm_config.get("require_convergence", False)),
    )

    updated_monthly = current_dfm_fit.dataset.monthly_features.reindex(
        columns=previous_dfm_fit.dataset.feature_names
    )
    updated_quarterly = current_dfm_fit.dataset.quarterly_target.rename(
        target_series
    ).to_frame()
    target_month = target_period.asfreq("M", how="end")
    news = previous_dfm_fit.results.news(
        updated_monthly,
        impact_date=target_month,
        impacted_variable=target_series,
        comparison_type="updated",
        revisions_details_start=-int(
            dfm_config.get("revision_details_periods", 60)
        ),
        endog_quarterly=updated_quarterly,
        original_scale=True,
    )

    previous_dfm_weight = previous_weights["Dynamic Factor Model"]
    dfm_news_raw = _target_value(news.update_impacts, target_series)
    dfm_revision_raw = _target_value(news.revision_impacts, target_series)
    dfm_post_fixed = _target_value(news.post_impacted_forecasts, target_series)
    if not np.isfinite(dfm_post_fixed):
        dfm_post_fixed = d0 + dfm_news_raw + dfm_revision_raw
    dfm_news_impact = dfm_news_raw * previous_dfm_weight
    dfm_revision_impact = dfm_revision_raw * previous_dfm_weight
    dfm_refit_impact = float(d1 - dfm_post_fixed) * previous_dfm_weight

    update_rows = _details_frame(
        news.details_by_update,
        "dfm_news",
        previous_dfm_weight,
        created_at,
    )
    revision_rows = _details_frame(
        news.revision_details_by_update,
        "dfm_revision",
        previous_dfm_weight,
        created_at,
    )
    detailed_revision_impact = float(revision_rows["impact"].sum()) if not revision_rows.empty else 0.0
    grouped_revision_impact = float(dfm_revision_impact - detailed_revision_impact)

    weight_change_impact = (
        (current_weights["Bridge Ridge"] - previous_weights["Bridge Ridge"]) * b1
        + (current_weights["Dynamic Factor Model"] - previous_weights["Dynamic Factor Model"]) * d1
    )
    explained = (
        bridge_data_impact
        + bridge_refit_impact
        + dfm_news_impact
        + dfm_revision_impact
        + dfm_refit_impact
        + weight_change_impact
    )
    residual = float(total_change - explained)

    contribution_frames = [
        frame
        for frame in [
            bridge_rows,
            update_rows,
            revision_rows,
            _aggregate_contribution(
                "dfm_revision_grouped",
                "Dynamic Factor Model",
                grouped_revision_impact,
                created_at,
            ),
            _aggregate_contribution("bridge_refit", "Bridge Ridge", bridge_refit_impact, created_at),
            _aggregate_contribution("dfm_refit", "Dynamic Factor Model", dfm_refit_impact, created_at),
            _aggregate_contribution("weight_change", "Production Ensemble", weight_change_impact, created_at),
            _aggregate_contribution("residual", "Production Ensemble", residual, created_at),
        ]
        if not frame.empty
    ]
    contributions = pd.concat(contribution_frames, ignore_index=True)
    contributions.insert(0, "decomposition_id", decomposition_id)

    release_changes = release_changes.copy()
    release_changes.insert(0, "decomposition_id", decomposition_id)
    release_changes["created_at"] = created_at

    details = {
        **base_details,
        "previous_weights": previous_weights,
        "current_weights": current_weights,
        "previous_components": {"Bridge Ridge": b0, "Dynamic Factor Model": d0},
        "current_components": {"Bridge Ridge": b1, "Dynamic Factor Model": d1},
        "bridge_fixed_current": bridge_fixed_current,
        "dfm_fixed_parameter_updated_forecast": dfm_post_fixed,
        "dfm_update_count": int(getattr(news, "data_updates", pd.DataFrame()).shape[0]),
        "dfm_revision_count": int(getattr(news, "data_revisions", pd.DataFrame()).shape[0]),
        "reconciliation_error": residual,
    }
    news_run = pd.DataFrame(
        [
            {
                "decomposition_id": decomposition_id,
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "target_period": str(target_period),
                "status": "success",
                "previous_forecast": previous_production,
                "current_forecast": current_production,
                "total_change": total_change,
                "bridge_data_impact": bridge_data_impact,
                "bridge_refit_impact": bridge_refit_impact,
                "dfm_news_impact": dfm_news_impact,
                "dfm_revision_impact": dfm_revision_impact,
                "dfm_refit_impact": dfm_refit_impact,
                "weight_change_impact": weight_change_impact,
                "residual_interaction": residual,
                "details_json": json.dumps(details),
                "created_at": created_at,
            }
        ]
    )
    repository.save_news_outputs(news_run, contributions, release_changes)
    return {
        "decomposition_id": decomposition_id,
        "status": "success",
        "previous_forecast": previous_production,
        "current_forecast": current_production,
        "total_change": total_change,
        "contributions": contributions,
        "release_changes": release_changes,
        "details": details,
    }


def _empty_news_result(
    repository: MacroRepository,
    decomposition_id: str,
    current_run_id: str,
    previous_run_id: str | None,
    target_period: pd.Period,
    status: str,
    release_changes: pd.DataFrame,
    details: dict[str, Any],
    created_at: datetime,
) -> dict[str, Any]:
    details = {**details, "message": status.replace("_", " ")}
    news_run = pd.DataFrame(
        [
            {
                "decomposition_id": decomposition_id,
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "target_period": str(target_period),
                "status": status,
                "previous_forecast": np.nan,
                "current_forecast": np.nan,
                "total_change": np.nan,
                "bridge_data_impact": np.nan,
                "bridge_refit_impact": np.nan,
                "dfm_news_impact": np.nan,
                "dfm_revision_impact": np.nan,
                "dfm_refit_impact": np.nan,
                "weight_change_impact": np.nan,
                "residual_interaction": np.nan,
                "details_json": json.dumps(details),
                "created_at": created_at,
            }
        ]
    )
    release_frame = release_changes.copy()
    if not release_frame.empty:
        release_frame.insert(0, "decomposition_id", decomposition_id)
        release_frame["created_at"] = created_at
    else:
        release_frame = pd.DataFrame(
            columns=[
                "decomposition_id",
                "series_id",
                "observation_date",
                "change_type",
                "previous_value",
                "current_value",
                "value_change",
                "created_at",
            ]
        )
    repository.save_news_outputs(news_run, pd.DataFrame(), release_frame)
    return {
        "decomposition_id": decomposition_id,
        "status": status,
        "contributions": pd.DataFrame(),
        "release_changes": release_frame,
        "details": details,
    }


def record_news_failure(
    repository: MacroRepository,
    current_run_id: str,
    previous_run_id: str | None,
    target_period: pd.Period | str,
    error: str,
) -> str:
    """Persist an attribution failure without affecting the completed nowcast."""
    decomposition_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(tzinfo=None)
    news_run = pd.DataFrame(
        [
            {
                "decomposition_id": decomposition_id,
                "current_run_id": current_run_id,
                "previous_run_id": previous_run_id,
                "target_period": str(target_period),
                "status": "failed",
                "previous_forecast": np.nan,
                "current_forecast": np.nan,
                "total_change": np.nan,
                "bridge_data_impact": np.nan,
                "bridge_refit_impact": np.nan,
                "dfm_news_impact": np.nan,
                "dfm_revision_impact": np.nan,
                "dfm_refit_impact": np.nan,
                "weight_change_impact": np.nan,
                "residual_interaction": np.nan,
                "details_json": json.dumps({"error": error}),
                "created_at": created_at,
            }
        ]
    )
    repository.save_news_outputs(news_run, pd.DataFrame(), pd.DataFrame())
    return decomposition_id

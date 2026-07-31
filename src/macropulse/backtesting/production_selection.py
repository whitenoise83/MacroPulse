from __future__ import annotations

from dataclasses import replace
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from macropulse.models.baseline import ForecastResult


STABLE_STAGE_POLICY_NAME = "Stable Stage Policy"
ROBUST_STAGE_ADAPTIVE_MODEL_NAME = "Robust Stage-Adaptive Policy"
# Backward-compatible import name used by older modules/tests.
STAGE_ADAPTIVE_MODEL_NAME = ROBUST_STAGE_ADAPTIVE_MODEL_NAME

ELIGIBLE_PRODUCTION_MODELS = (
    "Bridge Ridge",
    "Dynamic Factor Model",
    "Bridge–DFM Ensemble",
    "Rolling Bridge–DFM Ensemble",
)

DEFAULT_STABLE_STAGE_POLICY: dict[str, str] = {
    "early_quarter": "Dynamic Factor Model",
    "after_month_1": "Dynamic Factor Model",
    "after_month_2": "Bridge–DFM Ensemble",
    "quarter_end": "Rolling Bridge–DFM Ensemble",
    "pre_advance_release": "Dynamic Factor Model",
}

DEFAULT_SCORE_WEIGHTS: dict[str, float] = {
    "rmse": 0.40,
    "mae": 0.25,
    "trimmed_rmse_10": 0.20,
    "p90_abs_error": 0.15,
}


def effective_bridge_dfm_weights(
    selected_model: str,
    rolling_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """Represent each production candidate as Bridge/DFM weights."""
    if selected_model == "Bridge Ridge":
        return {"Bridge Ridge": 1.0, "Dynamic Factor Model": 0.0}
    if selected_model == "Dynamic Factor Model":
        return {"Bridge Ridge": 0.0, "Dynamic Factor Model": 1.0}
    if selected_model == "Bridge–DFM Ensemble":
        return {"Bridge Ridge": 0.5, "Dynamic Factor Model": 0.5}
    if selected_model == "Rolling Bridge–DFM Ensemble":
        weights = rolling_weights or {
            "Bridge Ridge": 0.5,
            "Dynamic Factor Model": 0.5,
        }
        bridge = max(float(weights.get("Bridge Ridge", 0.0)), 0.0)
        dfm = max(float(weights.get("Dynamic Factor Model", 0.0)), 0.0)
        total = bridge + dfm
        if total <= 0:
            return {"Bridge Ridge": 0.5, "Dynamic Factor Model": 0.5}
        return {
            "Bridge Ridge": bridge / total,
            "Dynamic Factor Model": dfm / total,
        }
    raise ValueError(f"Unsupported production model: {selected_model}")


def stable_component_for_stage(
    forecast_stage: str,
    policy: Mapping[str, str] | None = None,
) -> str:
    mapping = dict(DEFAULT_STABLE_STAGE_POLICY)
    if policy:
        mapping.update({str(key): str(value) for key, value in policy.items()})
    if forecast_stage not in mapping:
        raise ValueError(f"No stable production component is declared for stage: {forecast_stage}")
    return mapping[forecast_stage]


def build_stable_stage_policy(
    candidates: list[ForecastResult],
    forecast_stage: str,
    policy: Mapping[str, str] | None = None,
    fallback_model: str = "Bridge Ridge",
) -> tuple[ForecastResult, dict]:
    candidate_map = {
        result.model_name: result
        for result in candidates
        if result.model_name in ELIGIBLE_PRODUCTION_MODELS
    }
    if not candidate_map:
        raise ValueError("No eligible production candidates were supplied.")

    declared = stable_component_for_stage(forecast_stage, policy)
    selected_name = declared if declared in candidate_map else fallback_model
    if selected_name not in candidate_map:
        selected_name = "Bridge Ridge" if "Bridge Ridge" in candidate_map else next(iter(candidate_map))
    selected = candidate_map[selected_name]
    diagnostics = {
        "method": "predeclared_stable_stage_policy",
        "forecast_stage": forecast_stage,
        "declared_component": declared,
        "selected_component": selected_name,
        "fallback_used": selected_name != declared,
        "fallback_model": fallback_model,
    }
    policy_result = replace(
        selected,
        model_name=STABLE_STAGE_POLICY_NAME,
        diagnostics={
            **selected.diagnostics,
            "selection": diagnostics,
            "selected_component": selected_name,
        },
    )
    return policy_result, diagnostics


def _selection_history(
    history: pd.DataFrame,
    model_names: Iterable[str],
    window: int,
) -> pd.DataFrame:
    required = {"model_name", "point_forecast", "actual", "forecast_date"}
    if history.empty or required.difference(history.columns):
        return pd.DataFrame()

    names = list(model_names)
    frame = history.loc[history["model_name"].isin(names)].dropna(
        subset=["point_forecast", "actual", "forecast_date"]
    ).copy()
    if frame.empty:
        return frame

    frame["forecast_date"] = pd.to_datetime(frame["forecast_date"])
    frame["selection_key"] = (
        frame["target_period"].astype(str)
        if "target_period" in frame.columns
        else frame["forecast_date"].dt.strftime("%Y-%m-%d")
    )
    common = frame.pivot_table(
        index="selection_key",
        columns="model_name",
        values="point_forecast",
        aggfunc="first",
    ).reindex(columns=names)
    common_keys = common.dropna().index
    frame = frame.loc[frame["selection_key"].isin(common_keys)].copy()
    ordered_keys = (
        frame.groupby("selection_key")["forecast_date"]
        .max()
        .sort_values()
        .index.tolist()
    )
    if window > 0:
        ordered_keys = ordered_keys[-window:]
    return frame.loc[frame["selection_key"].isin(ordered_keys)].copy()


def _upper_trimmed_rmse(squared_errors: pd.Series, trim_fraction: float = 0.10) -> float:
    values = np.sort(squared_errors.dropna().to_numpy(dtype=float))
    if values.size == 0:
        return float("nan")
    remove = int(np.floor(values.size * trim_fraction))
    if remove > 0 and values.size - remove >= 1:
        values = values[:-remove]
    return float(np.sqrt(values.mean()))


def _robust_scorecard(
    sample: pd.DataFrame,
    model_names: list[str],
    score_weights: Mapping[str, float],
) -> pd.DataFrame:
    frame = sample.copy()
    frame["error"] = frame["point_forecast"] - frame["actual"]
    frame["abs_error"] = frame["error"].abs()
    frame["squared_error"] = frame["error"].pow(2)

    rows: list[dict] = []
    for model_name, group in frame.groupby("model_name"):
        if model_name not in model_names:
            continue
        rows.append(
            {
                "model_name": model_name,
                "observations": int(len(group)),
                "rmse": float(np.sqrt(group["squared_error"].mean())),
                "mae": float(group["abs_error"].mean()),
                "trimmed_rmse_10": _upper_trimmed_rmse(group["squared_error"]),
                "p90_abs_error": float(group["abs_error"].quantile(0.90)),
                "max_abs_error": float(group["abs_error"].max()),
            }
        )
    metrics = pd.DataFrame(rows).set_index("model_name") if rows else pd.DataFrame()
    if metrics.empty:
        return metrics

    weights = {str(key): float(value) for key, value in score_weights.items()}
    total_weight = sum(max(value, 0.0) for value in weights.values())
    if total_weight <= 0:
        weights = dict(DEFAULT_SCORE_WEIGHTS)
        total_weight = sum(weights.values())
    weights = {key: max(value, 0.0) / total_weight for key, value in weights.items()}

    score = pd.Series(0.0, index=metrics.index, dtype=float)
    for metric_name, weight in weights.items():
        if metric_name not in metrics.columns:
            continue
        best = float(metrics[metric_name].min())
        denominator = max(best, 1e-12)
        metrics[f"{metric_name}_relative"] = metrics[metric_name] / denominator
        score = score + weight * metrics[f"{metric_name}_relative"]
    metrics["robust_score"] = score
    return metrics.sort_values(["robust_score", "rmse", "mae"])


def select_robust_stage_candidate(
    candidates: list[ForecastResult],
    prior_results: pd.DataFrame,
    forecast_stage: str,
    incumbent_model: str | None = None,
    stable_policy: Mapping[str, str] | None = None,
    window: int = 20,
    min_history: int = 20,
    switch_threshold: float = 0.05,
    tail_ratio_limit: float = 1.10,
    maximum_error_ratio_limit: float = 1.25,
    score_weights: Mapping[str, float] | None = None,
    fallback_model: str = "Bridge Ridge",
) -> tuple[ForecastResult, dict]:
    """Select a stage candidate with robust metrics and switching discipline.

    The caller must provide only outcomes known before the current forecast.
    A challenger must improve the composite score by the declared threshold and
    pass tail-risk guards before replacing the incumbent.
    """
    candidate_map = {
        result.model_name: result
        for result in candidates
        if result.model_name in ELIGIBLE_PRODUCTION_MODELS
    }
    if not candidate_map:
        raise ValueError("No eligible production candidates were supplied.")

    declared_stable = stable_component_for_stage(forecast_stage, stable_policy)
    default_incumbent = declared_stable if declared_stable in candidate_map else fallback_model
    if default_incumbent not in candidate_map:
        default_incumbent = "Bridge Ridge" if "Bridge Ridge" in candidate_map else next(iter(candidate_map))
    incumbent = incumbent_model if incumbent_model in candidate_map else default_incumbent

    diagnostics: dict = {
        "method": "stable_incumbent_fallback",
        "forecast_stage": forecast_stage,
        "selected_component": incumbent,
        "incumbent_component": incumbent,
        "stable_component": declared_stable,
        "window": int(window),
        "min_history": int(min_history),
        "switch_threshold": float(switch_threshold),
        "tail_ratio_limit": float(tail_ratio_limit),
        "maximum_error_ratio_limit": float(maximum_error_ratio_limit),
        "common_history": 0,
        "max_prior_forecast_date": None,
        "switched": False,
        "switch_reason": "insufficient_history",
        "scorecard": {},
    }

    names = [name for name in ELIGIBLE_PRODUCTION_MODELS if name in candidate_map]
    sample = _selection_history(prior_results, names, window)
    if not sample.empty:
        diagnostics["common_history"] = int(sample["selection_key"].nunique())
        diagnostics["max_prior_forecast_date"] = (
            pd.to_datetime(sample["forecast_date"]).max().date().isoformat()
        )

    selected_name = incumbent
    if diagnostics["common_history"] >= min_history:
        weights = score_weights or DEFAULT_SCORE_WEIGHTS
        scorecard = _robust_scorecard(sample, names, weights)
        if not scorecard.empty and incumbent in scorecard.index:
            diagnostics["scorecard"] = {
                str(name): {
                    key: float(value)
                    for key, value in row.items()
                    if key != "observations" and np.isfinite(value)
                }
                | {"observations": int(row["observations"])}
                for name, row in scorecard.iterrows()
            }
            challenger = str(scorecard.index[0])
            incumbent_score = float(scorecard.loc[incumbent, "robust_score"])
            challenger_score = float(scorecard.loc[challenger, "robust_score"])
            required_score = incumbent_score * (1.0 - switch_threshold)
            tail_ok = float(scorecard.loc[challenger, "p90_abs_error"]) <= (
                float(scorecard.loc[incumbent, "p90_abs_error"]) * tail_ratio_limit
            )
            max_ok = float(scorecard.loc[challenger, "max_abs_error"]) <= (
                float(scorecard.loc[incumbent, "max_abs_error"]) * maximum_error_ratio_limit
            )

            diagnostics.update(
                {
                    "method": "robust_prior_common_sample",
                    "challenger_component": challenger,
                    "incumbent_score": incumbent_score,
                    "challenger_score": challenger_score,
                    "required_challenger_score": required_score,
                    "tail_guard_passed": bool(tail_ok),
                    "maximum_error_guard_passed": bool(max_ok),
                }
            )
            if challenger == incumbent:
                diagnostics["switch_reason"] = "incumbent_remains_best"
            elif challenger_score <= required_score and tail_ok and max_ok:
                selected_name = challenger
                diagnostics["switched"] = True
                diagnostics["switch_reason"] = "material_robust_score_improvement"
            else:
                if challenger_score > required_score:
                    reason = "improvement_below_switch_threshold"
                elif not tail_ok:
                    reason = "tail_risk_guard"
                else:
                    reason = "maximum_error_guard"
                diagnostics["switch_reason"] = reason
        else:
            diagnostics["switch_reason"] = "scorecard_unavailable"

    diagnostics["selected_component"] = selected_name
    selected = candidate_map[selected_name]
    champion = replace(
        selected,
        model_name=ROBUST_STAGE_ADAPTIVE_MODEL_NAME,
        diagnostics={
            **selected.diagnostics,
            "selection": diagnostics,
            "selected_component": selected_name,
        },
    )
    return champion, diagnostics


def select_stage_adaptive_candidate(
    candidates: list[ForecastResult],
    prior_results: pd.DataFrame,
    window: int = 20,
    min_history: int = 20,
    fallback_model: str = "Bridge–DFM Ensemble",
    forecast_stage: str = "quarter_end",
) -> tuple[ForecastResult, dict]:
    """Backward-compatible wrapper for the robust selector."""
    return select_robust_stage_candidate(
        candidates=candidates,
        prior_results=prior_results,
        forecast_stage=forecast_stage,
        incumbent_model=fallback_model,
        window=window,
        min_history=min_history,
        fallback_model=fallback_model,
    )
